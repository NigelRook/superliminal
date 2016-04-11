import pytest
from string import Template
import re
import tempfile
from tornado.web import Application, RequestHandler
from tornado.httpserver import HTTPServer
from tornado.httpclient import HTTPRequest
from tornado.testing import get_unused_port

API_KEY = '0123456789abcdef0123456789abcdef'
SERIES_ID = 101
SERIES_TITLE = "The Series"
SERIES_TVDB_ID = 987654
EPISODE_ID = 1001
EPISODE_NUMBER = 5
SEASON_NUMBER = 2
EPISODE_TITLE = "Episode Title"
EPISODE_FILE_ID = 501
EPISODE_FILE_QUALITY = "HDTV-720p"
EPISODE_FILE_QUALITY_VERSION = 1
EPISODE_FILE_RELEASE_GROUP = "TvRG"
EPISODE_FILE_SCENE_NAME = "The.Series.S02E05.HDTV.720p.H264-TvRG"
EPISODE_FILE_SIZE = "876543210"

def get_string_mapping(series_path="", video_filename=""):
    return {
        'SERIES_ID': SERIES_ID,
        'SERIES_TITLE': SERIES_TITLE,
        'SERIES_TVDB_ID': SERIES_TVDB_ID,
        'EPISODE_ID': EPISODE_ID,
        'EPISODE_NUMBER': EPISODE_NUMBER,
        'SEASON_NUMBER': SEASON_NUMBER,
        'EPISODE_TITLE': EPISODE_TITLE,
        'EPISODE_FILE_ID': EPISODE_FILE_ID,
        'EPISODE_FILE_QUALITY': EPISODE_FILE_QUALITY,
        'EPISODE_FILE_QUALITY_VERSION': EPISODE_FILE_QUALITY_VERSION,
        'EPISODE_FILE_RELEASE_GROUP': EPISODE_FILE_RELEASE_GROUP,
        'EPISODE_FILE_SCENE_NAME': EPISODE_FILE_SCENE_NAME,
        'EPISODE_FILE_SIZE': EPISODE_FILE_SIZE,
        'SERIES_PATH': series_path,
        'PATH': video_filename,
        'RELATIVE_PATH': (video_filename[len(tempfile.tempdir):]
                if video_filename.startswith(tempfile.tempdir)
                else "")
    }

class FakeSonarr(object):
    def __init__(self, video_filename):
        self.port = get_unused_port()
        app = Application([
            ('/api/Episode/(\d+)', FakeSonarr.EpisodeHandler),
            ('/api/EpisodeFile/(\d+)', FakeSonarr.EpisodeFileHandler, dict(video_filename=video_filename))
        ])
        self.server = HTTPServer(app)
        self.server.listen(self.port)
        self.url = 'http://localhost:%s' % (self.port,)

    def get_webhook_request(self, url):
        message = Template('''
        {
            "EventType": "Download",
            "Series": {
                "Id": ${SERIES_ID},
                "Title": "${SERIES_TITLE}",
                "Path": "${SERIES_PATH}",
                "TvdbId": ${SERIES_TVDB_ID}
            },
            "Episodes": [{
                "Id": ${EPISODE_ID},
                "EpisodeNumber": ${EPISODE_NUMBER},
                "SeasonNumber": ${SEASON_NUMBER},
                "Title": "${EPISODE_TITLE}",
                "Quality": "${EPISODE_FILE_QUALITY}",
                "QualityVersion": ${EPISODE_FILE_QUALITY_VERSION},
                "ReleaseGroup": "${EPISODE_FILE_RELEASE_GROUP}",
                "SceneName": "${EPISODE_FILE_SCENE_NAME}"
            }]
        }''').substitute(get_string_mapping(series_path=tempfile.tempdir))
        return HTTPRequest(url, method='POST',
            headers={'Content-Type':'application/json'},
            body=re.sub(r'\s+', '', message))

    class EpisodeHandler(RequestHandler):
        def get(self, episode_id):
            if self.request.headers['X-Api-Key'] != API_KEY:
                self.set_status(403)
                return
            if int(episode_id) != EPISODE_ID:
                self.set_status(404)
                return
            response = Template('''
            {
                "seriesId": ${SERIES_ID},
                "episodeFileId": ${EPISODE_FILE_ID},
                "seasonNumber": ${SEASON_NUMBER},
                "episodeNumber": ${EPISODE_NUMBER},
                "title": "${EPISODE_TITLE}",
                "hasFile": true,
                "monitored": true,
                "downloading": false,
                "id": ${EPISODE_ID}
            }''').substitute(get_string_mapping())
            self.set_header('Content-Type', 'application/json')
            self.write(re.sub(r"\s+", "", response))

    class EpisodeFileHandler(RequestHandler):
        def initialize(self, video_filename=None):
            self.video_filename = video_filename

        def get(self, episode_file_id):
            if self.request.headers['X-Api-Key'] != API_KEY:
                self.set_status(403)
                return
            if int(episode_file_id) != EPISODE_FILE_ID:
                self.set_status(404)
                return
            response = Template('''
            {
                "seriesId": ${SERIES_ID},
                "seasonNumber": ${SEASON_NUMBER},
                "relativePath": "${RELATIVE_PATH}",
                "path": "${PATH}",
                "sceneName": "${EPISODE_FILE_SCENE_NAME}",
                "size": ${EPISODE_FILE_SIZE},
                "quality": {
                    "quality": {
                        "id": ${EPISODE_FILE_QUALITY_VERSION},
                        "name": "${EPISODE_FILE_QUALITY}"
                    },
                    "revision": {
                        "version": 1,
                        "real": 0
                    }
                },
                "qualityCutoffNotMet": false,
                "id": ${EPISODE_FILE_ID}
            }''').substitute(get_string_mapping(series_path=tempfile.tempdir, video_filename=self.video_filename))
            self.set_header('Content-Type', 'application/json')
            self.write(re.sub(r"\s+", "", response))


    def finalize(self):
        self.server.stop()
