import pytest
from string import Template
import re
import tempfile
from tornado.web import Application, RequestHandler
from tornado.httpserver import HTTPServer
from tornado.httpclient import HTTPRequest
from tornado.testing import get_unused_port

API_KEY = "1234567890abcdef1234567890abcdef"
MOVIE_IMDB_ID = "tt9876543"
MOVIE_TITLE = "Movie Title"
MOVIE_YEAR = "2016"
MOVIE_RELEASE_GROUP = "FakeRG"
MOVIE_RELEASE_ID = "890abc1234567def890abc1234567def"
MOVIE_RELEASE_NAME = "Movie.Name.2016.1080p.WEBRip.h264-FakeRG"
MOVIE_RELEASE_QUALITY = "brrip"

def get_string_mapping(video_filename=""):
    return {
        'MOVIE_IMDB_ID': MOVIE_IMDB_ID,
        'MOVIE_TITLE': MOVIE_TITLE,
        'MOVIE_YEAR': MOVIE_YEAR,
        'MOVIE_RELEASE_GROUP': MOVIE_RELEASE_GROUP,
        'MOVIE_RELEASE_ID': MOVIE_RELEASE_ID,
        'MOVIE_RELEASE_NAME': MOVIE_RELEASE_NAME,
        'MOVIE_RELEASE_QUALITY': MOVIE_RELEASE_QUALITY,
        'PATH': video_filename
    }

class FakeCouchPotato:
    def __init__(self, video_filename):
        self.port = get_unused_port()
        self.movie_id = 'tt9876543'
        app = Application([
            ('/api/'+API_KEY+'/media.get', FakeCouchPotato.MediaDotGetHandler, dict(video_filename=video_filename))
        ])
        self.server = HTTPServer(app)
        self.server.listen(self.port)
        self.url = 'http://localhost:%s' % (self.port,)

    def get_webhook_request(self, url):
        return HTTPRequest(url, method='POST',
            headers={'Content-Type':'application/x-www-form-urlencoded'},
            body='message=Downloaded+Movie+Name+%28brrip%29&imdb_id='+self.movie_id)

    def finalize(self):
        self.server.stop()

    class MediaDotGetHandler(RequestHandler):
        def initialize(self, video_filename=""):
            self.video_filename = video_filename

        def get(self):
            response = Template('''
            {
                "media": {
                    "releases": [{
                        "status": "downloaded",
                        "info": {
                            "protocol": "nzb",
                            "description": "",
                            "name": "${MOVIE_RELEASE_NAME}",
                            "url": "https://nzb.site/getnzb/abcdef12345609877890654321fedcba12345678.nzb",
                            "age": 105,
                            "name_extra": "",
                            "seed_ratio": "",
                            "content": "${MOVIE_RELEASE_NAME}",
                            "score": 191,
                            "provider": "Newznab",
                            "seed_time": "",
                            "provider_extra": ", nzb.site",
                            "detail_url": "https://nzb.site/details/abcdef12345609877890654321fedcba12345678",
                            "type": "movie",
                            "id": "abcdef12345609877890654321fedcba12345678",
                            "size": 1476
                        },
                        "download_info": {
                            "status_support": true,
                            "id": "SABnzbd_nzo_1ABCDe",
                            "downloader": "Sabnzbd"
                        },
                        "identifier": "54321abcdef0987654321abcdef09876",
                        "media_id": "67890abcdef1234567890abcdef12345",
                        "_rev": "00016ab4",
                        "_t": "release",
                        "is_3d": 0,
                        "last_edit": 1458331518,
                        "_id": "890abc1234567def890abc1234567def",
                        "quality": "${MOVIE_RELEASE_QUALITY}",
                        "files": {
                            "movie": ["${PATH}"]
                        }
                    }]
                }
            }''').substitute(get_string_mapping(video_filename=self.video_filename))
            self.set_header('Content-Type', 'application/json')
            self.write(re.sub(r"\s+", "", response))
