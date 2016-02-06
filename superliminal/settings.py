import logging
import ConfigParser
import json
from subliminal import provider_manager
from babelfish import Language

logger = logging.getLogger(__name__)

class Settings:
    def __init__(self, path):
        self._parser = ConfigParser.RawConfigParser()

        self._parser.add_section('general')
        self._parser.set('general', 'languages', json.dumps(['en']))
        self._parser.set('general', 'providers', json.dumps(sorted([p.name for p in provider_manager])))
        self._parser.set('general', 'search_interval_hours', str(24))
        self._parser.set('general', 'search_for_days', str(7))
        self._parser.set('general', 'min_movie_score', str(62))
        self._parser.set('general', 'min_episode_score', str(137))
        self._parser.set('general', 'desired_movie_score', str(88))
        self._parser.set('general', 'desired_episode_score', str(204))

        self._parser.add_section('sonarr')
        self._parser.set('sonarr', 'url', 'http://localhost:8989')
        self._parser.set('sonarr', 'apikey', '')

        logger.info("Loading settings from %s", path)
        self._parser.read(path)

        logger.debug("languages=%s", self.languages)
        logger.debug("providers=%s", self.providers)
        logger.debug("search_interval_hours=%d", self.search_interval_hours)
        logger.debug("search_for_days=%d", self.search_for_days)
        logger.debug("min_movie_score=%d", self.min_movie_score)
        logger.debug("min_episode_score=%d", self.min_episode_score)
        logger.debug("desired_movie_score=%d", self.desired_movie_score)
        logger.debug("desired_episode_score=%d", self.desired_episode_score)
        logger.debug("provider_configs=%s", self.provider_configs)

        try:
            with open(path, 'w') as configfile:
                self._parser.write(configfile)
        except Exception as e:
            logger.debug("Failed writing back settings: %s", e)
            pass

    @property
    def languages(self):
        return {Language.fromietf(l) for l in json.loads(self._parser.get('general', 'languages'))}

    @property
    def providers(self):
        return json.loads(self._parser.get('general', 'providers'))

    @property
    def search_interval_hours(self):
        return int(self._parser.get('general', 'search_interval_hours'))

    @property
    def search_for_days(self):
        return int(self._parser.get('general', 'search_for_days'))

    @property
    def min_movie_score(self):
        return int(self._parser.get('general', 'min_movie_score'))

    @property
    def min_episode_score(self):
        return int(self._parser.get('general', 'min_episode_score'))

    @property
    def desired_movie_score(self):
        return int(self._parser.get('general', 'desired_movie_score'))

    @property
    def desired_episode_score(self):
        return int(self._parser.get('general', 'desired_episode_score'))

    @property
    def provider_configs(self):
        rv = {}
        for provider in provider_manager:
            if self._parser.has_section(provider.name):
                rv[provider.name] = {k: v for k, v in self._parser.items(provider.name)}
        return rv

    @property
    def sonarr_url(self):
        return self._parser.get('sonarr', 'url')

    @property
    def sonarr_api_key(self):
        return self._parser.get('sonarr', 'apikey')
