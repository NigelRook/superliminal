import logging
from tornado.web import RequestHandler, Application
from tornado.ioloop import IOLoop
from tornado.escape import json_decode
from tornado.httpserver import HTTPServer
from tornado.httpclient import HTTPClient, HTTPRequest

logger = logging.getLogger(__name__)

class AddHandler(RequestHandler):
    def initialize(self, core_factory):
        self._core = core_factory.get()

    def post(self):
        data = json_decode(self.request.body)
        path = data['path']
        name = data['name'] if 'name' in data else data['path']
        logger.info("ADD: %s -> %s", path, name)
        with self._core:
            self._core.add_video(path, name)

class SonarrHandler(RequestHandler):
    def initialize(self, core_factory):
        self._core = core_factory.get()

    def post(self):
        data = json_decode(self.request.body)
        event_type = data['EventType']
        if event_type in ['Test', 'Rename']:
            return

        http_client = HTTPClient()
        with self._core:
            for episode in data['Episodes']:
                id = episode['Id']
                headers = {'X-Api-Key':self._core.settings.sonarr_api_key}

                request = HTTPRequest(
                    method='GET', headers=headers,
                    url='%s/api/Episode/%d' % (self._core.settings.sonarr_url, id))
                response = http_client.fetch(request)
                episode_data = json_decode(response.body)

                file_id = episode_data['episodeFileId']
                request = HTTPRequest(
                    method='GET', headers=headers,
                    url='%s/api/EpisodeFile/%d' % (self._core.settings.sonarr_url, file_id))
                response = http_client.fetch(request)
                file_data = json_decode(response.body)

                path = file_data['path']
                name = file_data['sceneName']
                logger.info("ADD: %s -> %s", path, name)
                self._core.add_video(path, name)

def run(core_factory):
    init_params = { 'core_factory': core_factory }
    routes = [
        ('/add', AddHandler, init_params),
        ('/add/sonarr', SonarrHandler, init_params)
    ]
    application = Application(routes)
    http_server = HTTPServer(application)
    http_server.listen(5000)
    try:
        IOLoop.current().start()
    finally:
        http_server.stop()
