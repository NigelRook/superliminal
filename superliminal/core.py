import logging
import subliminal
import os
import io
from babelfish import Language
from datetime import datetime, timedelta
from tornado.queues import Queue
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor

from . import env, datastore

logger = logging.getLogger(__name__)


class SuperliminalCore:
    q = Queue()
    executor = ThreadPoolExecutor(max_workers=1)

    @classmethod
    def start_consumer(cls):
        IOLoop.current().spawn_callback(cls.consume)

    @classmethod
    @gen.coroutine
    def consume(cls):
        while True:
            (fun, args) = yield cls.q.get()
            try:
                yield cls.with_instance(fun, args)
            finally:
                cls.q.task_done()

    def __init__(self):
        logger.debug("Connecting to providers")
        self._provider_pool = subliminal.api.ProviderPool(
            providers=env.settings.providers, provider_configs=env.settings.provider_configs)
        logger.debug("Connecting to data store")
        self._datastore = datastore.SqLiteDataStore(env.paths.db_path)

    def close(self):
        logger.debug("Disconnecting from providers")
        self._provider_pool.terminate()
        logger.debug("Disconnecting from data store")
        self._datastore.close()

    @classmethod
    @run_on_executor
    def with_instance(cls, fun, args):
        core = cls()
        try:
            fun(core, *args)
        finally:
            core.close()

    def _add_video(self, path, name):
        logger.debug("add_video(%s, %s)", path, name)
        v = subliminal.video.Video.fromname(name)
        v.size = os.path.getsize(path)
        v.hashes = {
            'opensubtitles': subliminal.video.hash_opensubtitles(path),
            'thesubdb': subliminal.video.hash_thesubdb(path),
            'napiprojekt': subliminal.video.hash_napiprojekt(path)
        }
        logger.debug("video=%s", v.__dict__)
        self._datastore.add_video(path, v)
        for lang in env.settings.languages:
            self._download_best_subtitles(path, v, lang, self._get_min_score(v))

    @staticmethod
    def _download_matches_sub(download, sub, language):
        return download['provider'] == sub.provider_name and download['sub_id'] == sub.id and download['lang'] == str(language)

    @staticmethod
    def _compute_score(matches, scores):
        return sum((scores[match] for match in matches))

    def _find_best_sub(self, path, video, language, subs, downloaded):
        logger.debug("_find_best_sub(%s, %s, %s, %s, %s)", path, video, language, subs, downloaded)
        fresh_subs = (sub for sub in subs if not any((self._download_matches_sub(download, sub, language) for download in downloaded)))
        with_scores = [(sub, self._compute_score(sub.get_matches(video), video.scores)) for sub in fresh_subs]
        if len(with_scores) == 0:
            return (None, 0)
        sub, score = max(with_scores, key=lambda (sub, score): score)
        logger.info("Found best subtitle for %s:%s (%d)", path, sub, score)
        return (sub, score)

    def _get_min_score(self, video):
        if isinstance(video, subliminal.video.Episode):
            return env.settings.min_episode_score
        else:
            return env.settings.min_movie_score

    def _download_best_subtitles(self, path, video, lang, min_score):
        logger.debug("_download_best_subtitles(%s, %s, %s, %d)", path, video, lang, min_score)
        subs = self._provider_pool.list_subtitles(video, {lang})
        all_downloaded = self._datastore.get_downloads_for_video(path)
        downloaded = all_downloaded[lang] if lang in all_downloaded else []
        sub, score = self._find_best_sub(path, video, lang, subs, downloaded)
        if score < min_score:
            return
        self._provider_pool.download_subtitle(sub)
        subtitle_path = subliminal.subtitle.get_subtitle_path(path, language=lang)
        with io.open(subtitle_path, 'wb') as f:
            f.write(sub.content)
        self._datastore.add_download(path, sub.provider_name, str(sub.id), lang, score)

    def _check_for_better(self):
        logger.debug("check_for_better()")
        ignore_older_than = datetime.utcnow() - timedelta(days=env.settings.search_for_days)
        incomplete_videos = self._datastore.get_incomplete_videos(
            env.settings.languages, env.settings.desired_movie_score, env.settings.desired_episode_score, ignore_older_than)
        for video in incomplete_videos:
            for need in video['needs']:
                self._download_best_subtitles(video['path'], video['video'], need['lang'], need['current_score'] + 1)

    @classmethod
    def add_video(cls, path, name):
        cls.q.put_nowait((cls._add_video, [path, name]))

    @classmethod
    def check_for_better(cls):
        cls.q.putnowait((cls._check_for_better, []))
