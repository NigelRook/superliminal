import os.path
from subliminal.video import Video, Movie, Episode
import logging
from babelfish import Language
from itertools import groupby
from datetime import datetime
from CodernityDB.database import Database
from CodernityDB.hash_index import HashIndex
from CodernityDB.tree_index import TreeBasedIndex
import hashlib


logger = logging.getLogger(__name__)

class Serializer:
    _EPISODE_TYPE_IDENTIFIER = '_superliminal_ep'
    _MOVIE_TYPE_IDENTIFIER = '_superliminal_mov'
    _DEFAULT_TYPE_IDENTIFIER = ''

    @classmethod
    def _get_video_type(cls, video):
        type = cls._DEFAULT_TYPE_IDENTIFIER
        if isinstance(video, Episode):
            type = cls._EPISODE_TYPE_IDENTIFIER
        elif isinstance(video, Movie):
            type = cls._MOVIE_TYPE_IDENTIFIER
        return type

    @classmethod
    def _serialize_fields(cls, src, fields, dest):
        for f in fields:
            if f in src.__dict__:
                dest[f] = src.__dict__[f]

    @classmethod
    def serialize_video(cls, v):
        data = {}
        type = cls._get_video_type(v)
        if type == cls._EPISODE_TYPE_IDENTIFIER:
            cls._serialize_fields(v, ['series', 'season', 'episode', 'title', 'year', 'tvdb_id'], data)
        elif type == cls._MOVIE_TYPE_IDENTIFIER:
            cls._serialize_fields(v, ['title', 'year'], data)

        cls._serialize_fields(v, ['name', 'format', 'release_group', 'resolution', 'video_codec', 'audio_codec', 'imdb_id', 'hashes', 'size'], data)
        return data, type

    @classmethod
    def deserialize_video(cls, type, data):
        logger.debug("Deserializing %s:%s", type, data)
        result = None
        if type == cls._EPISODE_TYPE_IDENTIFIER:
            result = Episode(**data)
        elif type == cls._MOVIE_TYPE_IDENTIFIER:
            result = Movie(**data)
        else:
            result = Video(**data)
        return result

class NoSuchVideoError(Exception):
    def __init__(self, path):
        self._path = path
    def __str__(self):
        return "Video at '%s' has not been added" ^ self._path

class PathIndex(HashIndex):
    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '16s'
        super(PathIndex, self).__init__(*args, **kwargs)

    def make_key_value(self, data):
        if data['_t'] != 'path':
            return None
        path = data['path']
        return self.make_key(path), None

    def make_key(self, path):
        return md5(path).digest()

class PathAddedIndex(TreeBasedIndex):
    def __init__(self, *args, **kwargs):
        kwargs['node_capacity'] = 13
        kwargs['key_format'] = '19s'
        super(PathAddedIndex, self).__init__(*args, **kwargs)

    def make_key_value(self, data):
        if data['_t'] != 'path':
            return None
        added = data['added']
        return self.make_key(added), None

    def make_key(self, added):
        return added

class CodernityDataStore(object):
    PATH_TYPE = 'path'

    def __init__(self, db_path):
        self.db = Database(db_path)
        if self.db.exists():
            self.db.open()
        else:
            self.db.create()
            path_index = PathIndex(self.db.path, 'path')
            self.db.add_index(path_index)
            path_added_index = PathAddedIndex(self.db.path, 'path_added')
            self.db.add_index(path_added_index)

    @classmethod
    def dt_str(cls, datetime):
        return datetime.isoformat()[0:19]

    def add_video(self, path, video, added=None):
        logger.debug("add_video(%s, %s, %s)", path, video, added)
        added = added or datetime.utcnow()

        existing = list(self.db.get_many('path', path, with_doc=True))

        video_data, video_type = Serializer.serialize_video(video)
        data = dict(_t=self.PATH_TYPE, path=path, video_data=video_data, video_type=video_type,
                    downloads=dict(), added=self.dt_str(added))
        self.db.insert(data)

        for existing_path in existing:
            self.db.delete(existing_path['doc'])

    def add_download(self, path, provider, sub_id, language, score):
        logger.debug("add_download(%s, %s, %s, %s, %d)", path, provider, sub_id, language, score)
        data = self.db.get('path', path, with_doc=True)
        path = data['doc']
        download = dict(provider=provider, sub_id=sub_id, lang=str(language), score=score)
        if str(language) in path['downloads']:
            path['downloads'][str(language)].append(download)
        else:
            path['downloads'][str(language)] = [download]
        self.db.update(path)

    def get_downloads_for_video(self, path):
        logger.debug("get_downloads_for_video(%s)", path)
        data = self.db.get('path', path, with_doc=True)
        return data['doc']['downloads']

    @staticmethod
    def exceeds_desired_score(video, score, desired_movie_score, desired_episode_score):
        if isinstance(video, Episode):
            return score >= desired_episode_score
        elif isinstance(video, Movie):
            return score >= desired_movie_score

    def get_incomplete_videos(self, languages, desired_movie_score, desired_episode_score, ignore_older_than):
        logger.debug("get_incomplete_videos(%s, %d, %d, %s)", languages, desired_movie_score, desired_episode_score, ignore_older_than)
        within_date = self.db.get_many('path_added', start=self.dt_str(ignore_older_than), with_doc=True)
        results = []
        for path in (data['doc'] for data in within_date):
            video = Serializer.deserialize_video(path['video_type'], path['video_data'])
            needs = []
            for lang in languages:
                if str(lang) in path['downloads']:
                    current_score = max(download['score'] for download in path['downloads'][str(lang)])
                    if not self.exceeds_desired_score(video, current_score, desired_movie_score, desired_episode_score):
                        needs.append(dict(lang=lang, current_score=current_score))
                else:
                    needs.append(dict(lang=lang, current_score=0))
            if needs:
                results.append(dict(path=path['path'], video=video, needs=needs))

        logger.debug("found %d incomplete videos: %s", len(results), results)
        return results

    def close(self):
        self.db.close()
