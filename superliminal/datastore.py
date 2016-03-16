import os.path
import sqlite3
from subliminal.video import Video, Movie, Episode
import json
import logging
from babelfish import Language
from itertools import groupby
from datetime import datetime

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
        return json.dumps(data), type

    @classmethod
    def deserialize_video(cls, type, json_data):
        data = json.loads(json_data)
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

class SqLiteDataStore:
    _init_sql = """
        CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY, path TEXT, data TEXT, type TEXT, added TEXT);
        CREATE TABLE IF NOT EXISTS downloads (id INTEGER PRIMARY KEY, video INTEGER REFERENCES videos ON DELETE CASCADE, provider TEXT, sub_id TEXT, language TEXT, score INTEGER, downloaded TEXT);
        CREATE INDEX IF NOT EXISTS ix_videos_path ON videos(path);
        CREATE INDEX IF NOT EXISTS fk_downloaded_videos ON downloads(video);
    """

    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_db()
        self._conn.row_factory = sqlite3.Row

    def _init_db(self):
        self._conn.executescript(self._init_sql)
        self._conn.commit()

    def add_video(self, path, video, added=None):
        logger.debug("add_video(%s, %s, %s)", path, video, added)
        added = added or datetime.utcnow()
        data, type = Serializer.serialize_video(video)
        self._conn.execute("DELETE FROM videos WHERE path = ?", (path,))
        self._conn.execute("INSERT INTO videos (path, data, type, added) VALUES (?, ?, ?, ?)", (path, data, type, str(added)))
        self._conn.commit()

    def add_download(self, path, provider, sub_id, language, score):
        logger.debug("add_download(%s, %s, %s, %s, %d)", path, provider, sub_id, language, score)
        video_id = self._get_video_id_from_path(path)
        self._conn.execute("INSERT INTO downloads (video, provider, sub_id, language, score, downloaded) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                           (video_id, provider, sub_id, str(language), score))
        self._conn.commit()

    def get_downloads_for_video(self, path):
        logger.debug("get_downloads_for_video(%s)", path)
        video_id = self._get_video_id_from_path(path)
        c = self._conn.cursor()
        c.execute("SELECT provider, sub_id, language, score FROM downloads WHERE video = ? ORDER BY language, score DESC", (video_id,))
        results = c.fetchall()
        extracted = (self._convert_subtitle_row(row) for row in results)
        by_lang = dict((lang, list(subs)) for lang, subs in groupby(extracted, lambda sub: sub['lang']))
        logger.debug("got %d downloads", len(results))
        return by_lang

    @staticmethod
    def _convert_subtitle_row(row):
        return {'provider': row['provider'], 'sub_id': row['sub_id'], 'lang': row['language'], 'score': row['score']}

    def _get_video_id_from_path(self, path):
        logger.debug("_get_video_id_from_path(%s)", path)
        c = self._conn.cursor()
        c.execute("SELECT id FROM videos WHERE path = ? ORDER BY added DESC LIMIT 1", (path,))
        video = c.fetchone()
        if video == None:
            raise NoSuchVideoError(path)
        logger.debug("found video id %d", video['id'])
        return video['id']

    def get_incomplete_videos(self, languages, desired_movie_score, desired_episode_score, ignore_older_than):
        logger.debug("get_incomplete_videos(%s, %d, %d, %s)", languages, desired_movie_score, desired_episode_score, ignore_older_than)
        incomplete = []
        for language in languages:
            c = self._conn.cursor()
            c.execute("""
                SELECT videos.path, videos.data, videos.type, MAX(downloads.score) AS score
                FROM videos
                LEFT JOIN downloads ON videos.id = downloads.video AND downloads.language = ?
                WHERE videos.added >= ?
                GROUP BY videos.id, downloads.language
                HAVING (
                    score IS NULL
                    OR (videos.type = ? AND score < ?)
                    OR (videos.type = ? AND score < ?)
                )
            """, (str(language), ignore_older_than, Serializer._MOVIE_TYPE_IDENTIFIER, desired_movie_score, Serializer._EPISODE_TYPE_IDENTIFIER, desired_episode_score))
            results = c.fetchall()
            for row in results:
                incomplete.append((row['path'], Serializer.deserialize_video(row['type'], row['data']), language, row['score'] or 0))

        keyfunc = lambda (path, video, lang, score): path
        grouped = groupby(sorted(incomplete, key=keyfunc), key=keyfunc)
        results = []
        for path, stuff in grouped:
            stuff = list(stuff)
            needs = [{'lang':lang, 'current_score':score} for (path, video, lang, score) in stuff]
            stuff[0][1]
            results.append({'path':path, 'video':video, 'needs':needs})

        logger.debug("found %d incomplete videos: %s", len(results), results)
        return results

    def close(self):
        self._conn.close()
