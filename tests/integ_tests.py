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
import tornado.httpserver
import tornado.httpclient
from tornado.testing import AsyncHTTPTestCase, gen_test
from mock import patch

import fakecouchpotato, fakesonarr

OPENSUBTITLES_HASH = '111111'
NAPIPROJEKT_HASH = '222222'
THESUBDB_HASH = '333333'
SUBTITLE_CONTENT = '''1
00:00:01,000 --> 00:00:02,000
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
            }),
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
        superliminal.env.settings['provider_configs']['fakesub']['subs'] = subtitles

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

class CouchPotatoTests(IntegrationTests):
    def __init__(self):
        super(CouchPotatoTests, self).__init__()
        self.cp = fakecouchpotato.FakeCouchPotato(self.video_filename)
        self.set_subtitles([{
            'id': 'theonlysub',
            'language': Language.fromietf('en'),
            'title': fakecouchpotato.MOVIE_TITLE,
            'year': fakecouchpotato.MOVIE_YEAR,
            'release_group': fakecouchpotato.MOVIE_RELEASE_GROUP,
            'content': SUBTITLE_CONTENT
        }])
        env.settings.couchpotato_url = self.cp.url
        env.settings.couchpotato_api_key = fakecouchpotato.API_KEY

    @gen_test
    def test_couchpotato_add(self):
        request = self.cp.get_webhook_request(self.get_url('/add/couchpotato'))
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)

    def tearDown(self):
        self.cp.finalize()
        super(CouchPotatoTests, self).tearDown()

class SonarrTests(IntegrationTests):
    def __init__(self):
        super(SonarrTests, self).__init__()
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
        env.settings.sonarr_url = self.sonarr.url
        env.settings.sonarr_api_key = fakesonarr.API_KEY

    def get_video_size(self):
        return fakesonarr.EPISODE_FILE_SIZE

    @gen_test
    def test_sonarr_add(self):
        request = self.sonarr.get_webhook_request(self.get_url('/add/sonarr'))
        response = yield self.http_client.fetch(request)
        self.assertEqual(200, response.code)

    def tearDown(self):
        self.sonarr.finalize()
        super(SonarrTests, self).tearDown()
