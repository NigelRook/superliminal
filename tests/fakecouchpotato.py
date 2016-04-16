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
MOVIE_TITLE = "Movie Name"
MOVIE_YEAR = "2016"
MOVIE_RELEASE_GROUP = "FakeRG"
MOVIE_RELEASE_ID = "890abc1234567def890abc1234567def"
MOVIE_RELEASE_NAME = "Movie.Name.2016.1080p.WEBRip.h264-FakeRG"
MOVIE_RELEASE_QUALITY = "brrip"

def get_string_mapping(video_filename="", release_status="downloaded"):
    return {
        'MOVIE_IMDB_ID': MOVIE_IMDB_ID,
        'MOVIE_TITLE': MOVIE_TITLE,
        'MOVIE_YEAR': MOVIE_YEAR,
        'MOVIE_RELEASE_GROUP': MOVIE_RELEASE_GROUP,
        'MOVIE_RELEASE_ID': MOVIE_RELEASE_ID,
        'MOVIE_RELEASE_NAME': MOVIE_RELEASE_NAME,
        'MOVIE_RELEASE_QUALITY': MOVIE_RELEASE_QUALITY,
        'PATH': video_filename,
        'RELEASE_STATUS': release_status
    }

class FakeCouchPotato(object):
    def __init__(self, video_filename):
        self.port = get_unused_port()
        self.movie_id = 'tt9876543'
        app = Application([
            ('/api/'+API_KEY+'/media.get', FakeCouchPotato.MediaDotGetHandler, dict(owner=self))
        ])
        self.server = HTTPServer(app)
        self.server.listen(self.port)
        self.url = 'http://localhost:%s' % (self.port,)
        self.video_filename = video_filename
        self.return_files_immediately = True

    def get_webhook_request(self, url):
        return HTTPRequest(url, method='POST',
            headers={'Content-Type':'application/x-www-form-urlencoded'},
            body='message=Downloaded+Movie+Name+%28brrip%29&imdb_id='+self.movie_id)

    def finalize(self):
        self.server.stop()

    class MediaDotGetHandler(RequestHandler):
        MOVIE_WITH_FILE_TEMPLATE = Template('''
            {
                "media": {
                    "releases": [{
                        "status": "${RELEASE_STATUS}",
                        "info": {
                            "protocol": "nzb",
                            "name": "${MOVIE_RELEASE_NAME}",
                            "url": "https://nzb.site/getnzb/abcdef12345609877890654321fedcba12345678.nzb",
                            "content": "${MOVIE_RELEASE_NAME}",
                            "provider": "Newznab",
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
                        "_id": "${MOVIE_RELEASE_ID}",
                        "quality": "${MOVIE_RELEASE_QUALITY}",
                        "files": {
                            "movie": ["${PATH}"]
                        }
                    }]
                },
                "success": true
            }''')

        MOVIE_WITHOUT_FILE_TEMPLATE = Template('''
            {
                "media": {
                    "releases": [{
                        "status": "${RELEASE_STATUS}",
                        "info": {
                            "protocol": "nzb",
                            "name": "${MOVIE_RELEASE_NAME}",
                            "url": "https://nzb.site/getnzb/abcdef12345609877890654321fedcba12345678.nzb",
                            "content": "${MOVIE_RELEASE_NAME}",
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
                        "_id": "${MOVIE_RELEASE_ID}",
                        "quality": "${MOVIE_RELEASE_QUALITY}"
                    }]
                },
                "success": true
            }''')

        def initialize(self, owner=None):
            self.owner = owner

        def get(self):
            if self.owner.return_files_immediately:
                template = self.MOVIE_WITH_FILE_TEMPLATE
            else:
                template = self.MOVIE_WITHOUT_FILE_TEMPLATE
            response = template.substitute(get_string_mapping(video_filename=self.owner.video_filename))
            self.set_header('Content-Type', 'application/json')
            self.write(re.sub(r"\s+", "", response))
