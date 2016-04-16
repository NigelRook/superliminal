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
import superliminal.env
import tornado.web
from tornado.httpclient import HTTPRequest
from tornado.testing import AsyncHTTPTestCase, gen_test
from mock import patch
import json

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

class FakeSettings(object):
    def __init__(self, languages=[Language.fromietf('en')],
                 min_movie_score=20, desired_movie_score=50,
                 min_episode_score=50, desired_episode_score=100,
                 providers=None, provider_configs=None,
                 couchpotato_url=None, couchpotato_api_key=None,
                 sonarr_url=None, sonarr_api_key=None):
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

class FakePaths(object):
    def __init__(self, db_path=None):
        self.db_path = db_path

class IntegrationTests(AsyncHTTPTestCase):
    def setUp(self):
        logger = logging.getLogger()
        logger.level = logging.DEBUG
        logger.addHandler(logging.StreamHandler(sys.stdout))
        super(IntegrationTests, self).setUp()
        self.db_file = tempfile.NamedTemporaryFile()
        self.settings_file = tempfile.NamedTemporaryFile()
        self.video_file = tempfile.NamedTemporaryFile(suffix='.mkv')
        self.db_filename = self.db_file.name
        self.settings_filename = self.settings_file.name
        self.video_filename = self.video_file.name
        paths = FakePaths(db_path=self.db_filename)
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

    def get_app(self):
        return create_application()

    def set_subtitles(self, subtitles):
        superliminal.env.settings.provider_configs['fakesub']['subs'] = subtitles

    def get_video_size(self):
        return 876543210;

    def assert_subtitle_contents_matches(self, expected_content=SUBTITLE_CONTENT, suffix='.en.srt'):
        expected_sub_filename = re.sub(r'\.mkv$', suffix, self.video_filename)
        with open(expected_sub_filename, 'r') as subfile:
            self.assertEqual(expected_content, subfile.read())

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()
        self.db_file.close()
        self.settings_file.close()
        self.video_file.close()

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
        self.assert_subtitle_contents_matches(SUBTITLE_CONTENT_2)
        request = self.get_add_request(name="Series.Title.S02E03.720p.WEB-DL.H264-TvRG.mkv")
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)
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
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT, suffix='.en.srt')
        self.assert_subtitle_contents_matches(expected_content=SUBTITLE_CONTENT_2, suffix='.pt-BR.srt')


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
        self.assert_subtitle_contents_matches()

    def tearDown(self):
        self.sonarr.finalize()
        super(SonarrTests, self).tearDown()
