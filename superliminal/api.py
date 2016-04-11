import logging
import os.path
from tornado.web import RequestHandler, Application
from tornado.escape import json_decode, url_escape
from tornado.httpclient import HTTPRequest, AsyncHTTPClient
from tornado.httputil import parse_body_arguments
from tornado import gen
from . import env
from .core import SuperliminalCore

logger = logging.getLogger(__name__)

class AddHandler(RequestHandler):
    def post(self):
        data = json_decode(self.request.body)
        path = data['path']
        name = data['name'] if 'name' in data else data['path']
        logger.info("ADD: %s -> %s", path, name)
        with SuperliminalCore() as core:
            self._core.add_video(path, name)


class CouchPotatoHandler(RequestHandler):
    @gen.coroutine
    def post(self):
        if ((not 'imdb_id' in self.request.body_arguments) or
            (not self.request.body_arguments['message'][0].startswith('Downloaded'))):
            logger.debug('Ignoring invalid call to /add/couchpotato. body:%s', self.request.body)
            return

        logger.debug('/add/couchpotato content-type:%s, body:%s',
                     self.request.headers['Content-Type'], self.request.body)

        logger.debug(self.request.body_arguments['imdb_id'])
        id = self.request.body_arguments['imdb_id'][0]

        http_client = AsyncHTTPClient()
        request = HTTPRequest(
            method='GET',
            url='%s/api/%s/media.get?id=%s' %
                (env.settings.couchpotato_url,
                 env.settings.couchpotato_api_key,
                 url_escape(id)))
        response = yield http_client.fetch(request)
        movie_data = json_decode(response.body)
        release = next((release for release in movie_data['media']['releases'] if release['status'] == 'downloaded'))
        logger.debug('release: %s', release)
        path = release['files']['movie'][0]
        name = release['info']['name'].strip()+os.path.splitext(path)[1]
        logger.info("ADD (couchpotato): %s -> %s", path, name)

        with SuperliminalCore() as core:
            core.add_video(path, name)


class SonarrHandler(RequestHandler):
    @gen.coroutine
    def post(self):
        data = json_decode(self.request.body)
        logger.debug('Sonarr download: %s', data)
        event_type = data['EventType']
        if event_type in ['Test', 'Rename']:
            return

        http_client = AsyncHTTPClient()
        with SuperliminalCore() as core:
            for episode in data['Episodes']:
                id = episode['Id']
                headers = {'X-Api-Key':env.settings.sonarr_api_key}

                request = HTTPRequest(
                    method='GET', headers=headers,
                    url='%s/api/Episode/%d' % (env.settings.sonarr_url, id))
                response = yield http_client.fetch(request)
                episode_data = json_decode(response.body)
                logger.debug('Sonarr episode data: %s', episode_data)

                file_id = episode_data['episodeFileId']
                request = HTTPRequest(
                    method='GET', headers=headers,
                    url='%s/api/EpisodeFile/%d' % (env.settings.sonarr_url, file_id))
                response = yield http_client.fetch(request)
                file_data = json_decode(response.body)
                logger.debug('Sonarr file data: %s', file_data)

                path = file_data['path']
                name = file_data['sceneName']+os.path.splitext(path)[1]
                logger.info("ADD (sonarr): %s -> %s", path, name)
                core.add_video(path, name)

def create_application():
    routes = [
        ('/add', AddHandler),
        ('/add/couchpotato', CouchPotatoHandler),
        ('/add/sonarr', SonarrHandler)
    ]
    return Application(routes)
