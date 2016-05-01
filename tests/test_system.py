import setpaths
import sys, os
import re
import pytest
import tempfile
import logging
from fakesubprovider import FakeProviderPool
from babelfish import Language
from superliminal.settings import Settings
from superliminal.api import create_application
from superliminal.core import SuperliminalCore
import superliminal.env
import tornado.web
from tornado import gen
from tornado.httpclient import HTTPRequest
from tornado.testing import AsyncHTTPTestCase, LogTrapTestCase, gen_test
from mock import patch
from freezegun import freeze_time
import json
from shutil import rmtree

import fakecouchpotato, fakesonarr

OPENSUBTITLES_HASH = '111111'
NAPIPROJEKT_HASH = '222222'
THESUBDB_HASH = '333333'
SUBTITLE_CONTENT = '''1
00:00:01,000 --> 00:00:02,000
Words that people are saying
'''
SUBTITLE_CONTENT_2 = '''1
00:00:02,000 --> 00:00:03,000
Words that people are saying
'''
SUBTITLE_CONTENT_3 = '''1
00:00:03,000 --> 00:00:04,000
Words that people are saying
'''

class FakeSettings(object):
    def __init__(self, languages=[Language.fromietf('en')],
                 min_movie_score=20, desired_movie_score=40,
                 min_episode_score=50, desired_episode_score=120,
                 providers=None, provider_configs=None,
                 couchpotato_url=None, couchpotato_api_key=None,
                 sonarr_url=None, sonarr_api_key=None,
                 search_for_days=7):
        self.languages = languages
        self.providers = providers
        self.provider_configs = provider_configs
        self.min_movie_score = min_movie_score
        self.desired_movie_score = desired_movie_score
        self.min_episode_score = min_episode_score
        self.desired_episode_score = desired_episode_score
        self.couchpotato_url = couchpotato_url
        self.couchpotato_api_key = couchpotato_api_key
        self.sonarr_url = sonarr_url
        self.sonarr_api_key = sonarr_api_key
        self.search_for_days = search_for_days

class FakePaths(object):
    def __init__(self, db_path=None):
        self.db_path = db_path

class IntegrationTests(AsyncHTTPTestCase, LogTrapTestCase):
    def setUp(self):
        super(IntegrationTests, self).setUp()
        SuperliminalCore.start_consumer()
        self.db_path = tempfile.mkdtemp()
        settings_file = tempfile.NamedTemporaryFile()
        self.tempfiles = [settings_file]
        self.settings_filename = settings_file.name
        self.video_filename = self.create_video_file()
        paths = FakePaths(db_path=self.db_path)
        superliminal.env.paths = paths
        fakesettings = FakeSettings(
            providers=['fakesub'],
            provider_configs={
                'fakesub': {
                    'languages': [Language.fromietf('en')],
                    'subs': []
                }
            })
        superliminal.env.settings = fakesettings
        self.patchers = []
        self.patchers.append(patch('subliminal.api.ProviderPool', wraps=FakeProviderPool))
        self.patchers.append(patch('subliminal.video.hash_opensubtitles', return_value=OPENSUBTITLES_HASH))
        self.patchers.append(patch('subliminal.video.hash_napiprojekt', return_value=NAPIPROJEKT_HASH))
        self.patchers.append(patch('subliminal.video.hash_thesubdb', return_value=THESUBDB_HASH))
        self.patchers.append(patch('os.path.getsize', return_value=self.get_video_size()))
        for patcher in self.patchers:
            patcher.start()

    def create_video_file(self):
        video_file = tempfile.NamedTemporaryFile(suffix='.mkv')
        self.tempfiles.append(video_file)
        return video_file.name

    def get_app(self):
        return create_application()

    def set_subtitles(self, subtitles):
        superliminal.env.settings.provider_configs['fakesub']['subs'] = subtitles

    def get_video_size(self):
        return 876543210;

    @staticmethod
    def transform_sub(source, new_id, **kwargs):
        result = source.copy()
        for key in kwargs:
            result[key] = kwargs[key]
        result['id'] = new_id
        return result

    def wait_until_processed(self):
        return SuperliminalCore.q.join()

    def subtitle_contents_matches(self, video_filename=None, expected_content=SUBTITLE_CONTENT, suffix='.en.srt'):
        video_filename = video_filename or self.video_filename
        expected_sub_filename = re.sub(r'\.mkv$', suffix, video_filename)
        if not os.path.isfile(expected_sub_filename):
            return False
        with open(expected_sub_filename, 'r') as subfile:
            return expected_content == subfile.read()

    def assert_no_subtitle(self, video_filename=None, suffix='.en.srt'):
        video_filename = video_filename or self.video_filename
        expected_sub_filename = re.sub(r'\.mkv$', suffix, video_filename)
        self.assertFalse(os.path.isfile(expected_sub_filename))

    def assert_subtitle_contents_matches(self, **kwargs):
        self.assertTrue(self.subtitle_contents_matches(**kwargs))

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()
        for tempfile in self.tempfiles:
            tempfile.close()
        rmtree(self.db_path)

    def enable_logging(self):
        logger = logging.getLogger()
        logger.level = logging.DEBUG
        logger.addHandler(logging.StreamHandler(sys.stdout))


class AddTests(IntegrationTests):
    def get_add_request(self, path=None, name=None):
        url = self.get_url('/add')
        path = path or self.video_filename
        body = {'path': path}
        if name:
            body['name'] = name
        return HTTPRequest(url, method='POST',
            headers={'Content-Type':'application/json'},
            body=json.dumps(body))

    @gen_test
    def test_add_tv_show(self):
        self.set_subtitles([{
            'id': 'theonlysub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "TvRG",
            'content': SUBTITLE_CONTENT
        }])
        request = self.get_add_request(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv")
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches()

    @gen_test
    def test_add_movie(self):
        self.set_subtitles([{
            'id': 'theonlysub',
            'language': Language.fromietf('en'),
            'title': "Movie Title",
            'year': 2016,
            'release_group': "MovieRG",
            'content': SUBTITLE_CONTENT
        }])
        request = self.get_add_request(name="Movie.Title.2016.720p.WEB-DL.H264-MovieRG.mkv")
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches()

    @gen_test
    def test_gets_best_match(self):
        self.set_subtitles([{
            'id': 'matching_sub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "TvRG",
            'resolution': '720p',
            'content': SUBTITLE_CONTENT
        },
        {
            'id': 'sub_with_wrong_release_group',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "OtherRG",
            'resolution': '720p',
            'content': SUBTITLE_CONTENT_2
        },
        {
            'id': 'sub_with_wrong_resolution',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "TvRG",
            'resolution': '1080p',
            'content': SUBTITLE_CONTENT_2
        }])
        request = self.get_add_request(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv")
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches()

    @gen_test
    def test_downloads_new_sub_if_new_video_added_for_existing_path(self):
        self.set_subtitles([{
            'id': 'new_sub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "TvRG",
            'resolution': '720p',
            'content': SUBTITLE_CONTENT
        },
        {
            'id': 'old_sub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "OtherRG",
            'resolution': '720p',
            'content': SUBTITLE_CONTENT_2
        }])
        request = self.get_add_request(name="Series.Title.S02E03.720p.WEB-DL.H264-OtherRG.mkv")
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        request = self.get_add_request(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv")
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches()

    @gen_test
    def test_downloads_for_all_configured_languages(self):
        superliminal.env.settings.languages.append(Language.fromietf('pt-BR'))
        self.set_subtitles([{
            'id': 'english_sub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "TvRG",
            'resolution': '720p',
            'content': SUBTITLE_CONTENT
        },
        {
            'id': 'brazilian_sub',
            'language': Language.fromietf('pt-BR'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "TvRG",
            'resolution': '720p',
            'content': SUBTITLE_CONTENT_2
        }])
        request = self.get_add_request(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv")
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT, suffix='.en.srt')
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT_2, suffix='.pt-BR.srt')

    @gen_test
    def test_doesnt_download_movie_below_score_threshold(self):
        superliminal.env.settings.min_movie_score = 100
        superliminal.env.settings.desired_movie_score = 100
        self.set_subtitles([{
            'id': 'theonlysub',
            'language': Language.fromietf('en'),
            'title': "Movie Title",
            'year': 2016,
            'release_group': "MovieRG",
            'content': SUBTITLE_CONTENT
        }])
        request = self.get_add_request(name="Movie.Title.2016.720p.WEB-DL.H264-MovieRG.mkv")
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        self.assert_no_subtitle()

    @gen_test
    def test_doesnt_download_episode_below_score_threshold(self):
        superliminal.env.settings.min_episode_score = 150
        superliminal.env.settings.desired_episode_score = 150
        self.set_subtitles([{
            'id': 'theonlysub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "TvRG",
            'content': SUBTITLE_CONTENT
        }])
        request = self.get_add_request(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv")
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        self.assert_no_subtitle()

class CheckForBetterTests(IntegrationTests):
    @gen.coroutine
    def add_video(self, path=None, name=None, subtitle=None):
        if subtitle:
            self.set_subtitles([subtitle])

        url = self.get_url('/add')
        path = path or self.video_filename
        body = {'path': path}
        if name:
            body['name'] = name
        request = HTTPRequest(url, method='POST',
            headers={'Content-Type':'application/json'},
            body=json.dumps(body))
        yield self.http_client.fetch(request)
        yield self.wait_until_processed()

    @gen_test
    def test_check_for_better_gets_better_sub_when_available(self):
        oksub = {
            'id': 'oksub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "OtherRG",
            'content': SUBTITLE_CONTENT
        }
        yield self.add_video(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv", subtitle=oksub)
        bettersub = self.transform_sub(oksub, 'bettersub', release_group="TvRG", content=SUBTITLE_CONTENT_2)

        self.set_subtitles([oksub, bettersub])
        SuperliminalCore.check_for_better()
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT_2)

    @gen_test
    def test_check_for_better_gets_subs_for_videos_with_no_subs(self):
        yield self.add_video(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv")

        oksub = {
            'id': 'oksub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "OtherRG",
            'content': SUBTITLE_CONTENT
        }

        self.set_subtitles([oksub])
        SuperliminalCore.check_for_better()
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT)

    @gen_test
    def test_check_for_better_checks_all_recent_videos(self):
        oktvsub = {
            'id': 'oktvsub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "OtherRG",
            'content': SUBTITLE_CONTENT
        }
        yield self.add_video(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv", subtitle=oktvsub)
        movie_filename = self.create_video_file()
        okmoviesub = {
            'id': 'okmoviesub',
            'language': Language.fromietf('en'),
            'title': "Movie Title",
            'year': 2016,
            'release_group': "OtherRG",
            'content': SUBTITLE_CONTENT
        }
        yield self.add_video(path=movie_filename,
            name="Movie.Title.2016.720p.WEB-DL.H264-MovieRG.mkv", subtitle=okmoviesub)

        bettertvsub = self.transform_sub(oktvsub, 'bettertvsub',
            release_group="TvRG", content=SUBTITLE_CONTENT_2)
        bettermoviesub = self.transform_sub(okmoviesub, 'bettermoviesub',
            release_group="MovieRG", content=SUBTITLE_CONTENT_3)
        self.set_subtitles([oktvsub, bettertvsub, okmoviesub, bettermoviesub])

        SuperliminalCore.check_for_better()
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT_2)
        self.assert_subtitle_contents_matches(video_filename=movie_filename,
            expected_content=SUBTITLE_CONTENT_3)

    @gen_test
    def test_check_for_better_checks_all_languages(self):
        superliminal.env.settings.languages.append(Language.fromietf('pt-BR'))
        okensub = {
            'id': 'okensub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "OtherRG",
            'content': SUBTITLE_CONTENT
        }
        okbrsub = self.transform_sub(okensub, 'okbrsub', language=Language.fromietf('pt-BR'))
        self.set_subtitles([okensub, okbrsub])
        yield self.add_video(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv")

        betterensub = self.transform_sub(okensub, 'betterensub',
            release_group="TvRG", content=SUBTITLE_CONTENT_2)
        betterbrsub = self.transform_sub(okbrsub, 'betterbrsub',
            release_group="TvRG", content=SUBTITLE_CONTENT_3)
        self.set_subtitles([okensub, betterensub, okbrsub, betterbrsub])

        SuperliminalCore.check_for_better()
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT_2, suffix='.en.srt')
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT_3, suffix='.pt-BR.srt')

    @gen_test
    def test_check_for_better_checks_languages_with_no_current_subs(self):
        superliminal.env.settings.languages.append(Language.fromietf('pt-BR'))
        okensub = {
            'id': 'okensub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "OtherRG",
            'content': SUBTITLE_CONTENT
        }
        self.set_subtitles([okensub])
        self.add_video(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv")
        yield self.wait_until_processed()

        betterensub = self.transform_sub(okensub, 'betterensub',
            release_group="TvRG", content=SUBTITLE_CONTENT_2)
        okbrsub = self.transform_sub(okensub, 'okbrsub',
            language=Language.fromietf('pt-BR'), content=SUBTITLE_CONTENT_3)
        self.set_subtitles([okensub, betterensub, okbrsub])

        SuperliminalCore.check_for_better()
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT_2, suffix='.en.srt')
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT_3, suffix='.pt-BR.srt')

    @gen_test
    def test_check_for_better_doesnt_get_new_worse_sub(self):
        superliminal.env.settings.desired_episode_score = 150
        oksub = {
            'id': 'oksub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "TvRG",
            'content': SUBTITLE_CONTENT
        }
        yield self.add_video(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv", subtitle=oksub)
        bettersub = self.transform_sub(oksub, 'bettersub', release_group="OtherRG", content=SUBTITLE_CONTENT_2)

        self.set_subtitles([oksub, bettersub])
        SuperliminalCore.check_for_better()
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT)

    @gen_test
    def test_check_for_better_doesnt_check_for_movies_already_having_subs_above_desired_score(self):
        superliminal.env.settings.desired_movie_score = 20
        okmoviesub = {
            'id': 'okmoviesub',
            'language': Language.fromietf('en'),
            'title': "Movie Title",
            'year': 2016,
            'release_group': "OtherRG",
            'content': SUBTITLE_CONTENT
        }
        yield self.add_video(name="Movie.Title.2016.720p.WEB-DL.H264-MovieRG.mkv", subtitle=okmoviesub)

        bettermoviesub = self.transform_sub(okmoviesub, 'bettermoviesub', release_group='MovieRG', content=SUBTITLE_CONTENT_2)
        self.set_subtitles([okmoviesub, bettermoviesub])

        SuperliminalCore.check_for_better()
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT)

    @gen_test
    def test_check_for_better_doesnt_check_for_episodes_already_having_subs_above_desired_score(self):
        superliminal.env.settings.desired_episode_score = 50
        oktvsub = {
            'id': 'oktvsub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "OtherRG",
            'content': SUBTITLE_CONTENT
        }
        yield self.add_video(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv", subtitle=oktvsub)

        bettertvsub = self.transform_sub(oktvsub, 'bettertvsub', release_group='TvRG', content=SUBTITLE_CONTENT_2)
        self.set_subtitles([oktvsub, bettertvsub])

        SuperliminalCore.check_for_better()
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT)

    @gen_test
    def test_check_for_better_doesnt_download_movie_subs_with_scores_below_min_threshold(self):
        superliminal.env.settings.min_movie_score = 100
        superliminal.env.settings.desired_movie_score = 100
        yield self.add_video(name="Movie.Title.2016.720p.WEB-DL.H264-MovieRG.mkv")

        okmoviesub = {
            'id': 'okmoviesub',
            'language': Language.fromietf('en'),
            'title': "Movie Title",
            'year': 2016,
            'release_group': "OtherRG",
            'content': SUBTITLE_CONTENT
        }
        self.set_subtitles([okmoviesub])

        SuperliminalCore.check_for_better()
        yield self.wait_until_processed()
        self.assert_no_subtitle()

    @gen_test
    def test_check_for_better_doesnt_get_subs_for_old_videos(self):
        oksub = {
            'id': 'oksub',
            'language': Language.fromietf('en'),
            'series': "Series Title",
            'season': 2,
            'episode': 3,
            'title': "The Episode",
            'release_group': "OtherRG",
            'content': SUBTITLE_CONTENT
        }
        from datetime import datetime, timedelta
        add_time = datetime.utcnow() - timedelta(days=7, seconds=1)
        with freeze_time(add_time):
            yield self.add_video(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv", subtitle=oksub)

        bettersub = self.transform_sub(oksub, 'bettersub', release_group="TvRG", content=SUBTITLE_CONTENT_2)

        self.set_subtitles([oksub, bettersub])
        SuperliminalCore.check_for_better()
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT)


class CouchPotatoTests(IntegrationTests):
    def setUp(self):
        super(CouchPotatoTests, self).setUp()
        self.cp = fakecouchpotato.FakeCouchPotato(self.video_filename)
        self.set_subtitles([{
            'id': 'theonlysub',
            'language': Language.fromietf('en'),
            'title': fakecouchpotato.MOVIE_TITLE,
            'year': fakecouchpotato.MOVIE_YEAR,
            'release_group': fakecouchpotato.MOVIE_RELEASE_GROUP,
            'content': SUBTITLE_CONTENT
        }])
        superliminal.env.settings.couchpotato_url = self.cp.url
        superliminal.env.settings.couchpotato_api_key = fakecouchpotato.API_KEY

    @gen_test
    def test_couchpotato_add(self):
        request = self.cp.get_webhook_request(self.get_url('/add/couchpotato'))
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches()

    @gen_test
    def test_couchpotato_add_with_files_not_known_immediately(self):
        from superliminal.api import CouchPotatoHandler
        CouchPotatoHandler.recheck_files_frequency = 0.05

        self.cp.return_files = False
        request = self.cp.get_webhook_request(self.get_url('/add/couchpotato'))
        response_fut = self.http_client.fetch(request)
        yield gen.sleep(0.1)

        self.cp.return_files = True
        response = yield response_fut

        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches()

    def tearDown(self):
        self.cp.finalize()
        super(CouchPotatoTests, self).tearDown()

class SonarrTests(IntegrationTests):
    def setUp(self):
        super(SonarrTests, self).setUp()
        self.sonarr = fakesonarr.FakeSonarr(self.video_filename)
        self.set_subtitles([{
            'id': 'theonlysub',
            'language': Language.fromietf('en'),
            'series': fakesonarr.SERIES_TITLE,
            'season': fakesonarr.SEASON_NUMBER,
            'episode': fakesonarr.EPISODE_NUMBER,
            'title': fakesonarr.EPISODE_TITLE,
            'release_group': fakesonarr.EPISODE_FILE_RELEASE_GROUP,
            'content': SUBTITLE_CONTENT
        }])
        superliminal.env.settings.sonarr_url = self.sonarr.url
        superliminal.env.settings.sonarr_api_key = fakesonarr.API_KEY

    def get_video_size(self):
        return fakesonarr.EPISODE_FILE_SIZE

    @gen_test
    def test_sonarr_add(self):
        request = self.sonarr.get_webhook_request(self.get_url('/add/sonarr'))
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
        yield self.wait_until_processed()
        self.assert_subtitle_contents_matches()

    def tearDown(self):
        self.sonarr.finalize()
        super(SonarrTests, self).tearDown()
