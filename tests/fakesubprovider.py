from subliminal.providers import Provider
from subliminal.subtitle import Subtitle
from subliminal.video import Episode, Movie

class FakeSub(Subtitle):
    def __init__(self, data):
        super(FakeSub, self).__init__(data['language'], data.get('hearing_impared', False), data.get('page_link'))
        self._data = data
        extract = lambda field, d: d[field] if field in d else None
        self.series = extract('series', data)
        self.season = extract('season', data)
        self.episode = extract('episode', data)
        self.title = extract('title', data)
        self.year = extract('year', data)
        self.release_group = extract('release_group', data)
        self.resolution = extract('resolution', data)
        self.format = extract('format', data)
        self.video_codec = extract('video_codec', data)
        self.audio_codec = extract('audio_codec', data)
        self.hash = extract('hash', data)
        self.size = extract('size', data)
  
    @property
    def id(self):
        return self._data['id']

    def get_matches(self, video, hearing_impaired=False):
        matches = super(FakeSub, self).get_matches(video, hearing_impaired=hearing_impaired)

        if isinstance(video, Episode):
            if video.series and video.series == self.series:
                matches.add('series')
            if video.season and self.season == video.season:
                matches.add('season')
            if video.episode and self.episode == video.episode:
                matches.add('episode')

        if video.title and self.title == video.title:
            matches.add('title')
        if video.year == self.year:
            matches.add('year')
        if video.release_group and self.release_group == video.release_group:
            matches.add('release_group')
        if video.resolution and self.resolution == video.resolution:
            matches.add('resolution')
        if video.format and self.format == video.format:
            matches.add('format')
        if video.video_codec and self.video_codec == video.video_codec:
            matches.add('video_codec')
        if video.audio_codec and self.audio_codec == video.audio_codec:
            matches.add('audio_codec')
        if video.hashes['opensubtitles'] and video.size and self.hash == video.hashes['opensubtitles'] and self.size == video.size:
            matches.add('hash')

        return matches

class FakeSubProvider(Provider):
    video_types = (Episode, Movie)
 
    def __init__(self, languages, subs):
        self.languages = languages
        self.subs = subs

    def initialize(self):
        pass

    def terminate(self):
        pass

    def query(self, languages):
        return [FakeSub(sub) for sub in self.subs if sub['language'] in languages]

    def list_subtitles(self, video, languages):
        return self.query(languages)

    def download_subtitle(self, subtitle):
        subtitle.content = next(sub['content'] for sub in self.subs if sub['id'] == subtitle.id)

class FakeProviderPool(object):
    def __init__(self, providers=None, provider_configs=None):
        if ('fakesub' in providers) and ('fakesub' in provider_configs):
            self.provider = FakeSubProvider(provider_configs['fakesub']['languages'],
                                            provider_configs['fakesub']['subs'])
        else:
            self.provider = None

    def list_subtitles(self, video, languages):
        if self.provider:
            return self.provider.list_subtitles(video, languages)
        else:
            return []

    def download_subtitle(self, subtitle):
        if self.provider:
            self.provider.download_subtitle(subtitle)

    def terminate(self):
        pass
