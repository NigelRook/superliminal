import logging
from tornado.web import RequestHandler, Application
from tornado.ioloop import IOLoop
from tornado.escape import json_decode
from tornado.httpserver import HTTPServer

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

def run(core_factory):
    init_params = { 'core_factory': core_factory }
    routes = [
        ('/add', AddHandler, init_params)
    ]
    application = Application(routes)
    http_server = HTTPServer(application)
    http_server.listen(5000)
    try:
        IOLoop.current().start()
    finally:
        http_server.stop()
