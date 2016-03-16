import logging
import datastore
import subliminal
import os
import io
import settings
from babelfish import Language
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SuperliminalCore:
    def __init__(self, settings, db_path):
        self._settings = settings
        self._db_path = db_path

    @property
    def settings(self):
	return self._settings

    def __enter__(self):
        logger.debug("Connecting to providers")
        self._provider_pool = subliminal.api.ProviderPool(
            providers=self._settings.providers, provider_configs=self._settings.provider_configs)
        logger.debug("Connecting to data store")
        self._datastore = datastore.SqLiteDataStore(self._db_path)
        return self

    def __exit__(self, type, value, traceback):
        logger.debug("Disconnecting from providers")
        self._provider_pool.terminate()
        logger.debug("Disconnecting from data store")
        self._datastore.close()
        return False

    def add_video(self, path, name):
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
        for lang in self._settings.languages:
            self._download_best_subtitles(path, v, lang, self._get_min_score(v))

    @staticmethod
    def _download_matches_sub(download, sub, language):
        return download['provider'] == sub.provider_name and download['sub_id'] == sub.id and download['language'] == str(language)

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
            return self._settings.min_episode_score
        else:
            return self._settings.min_movie_score

    def _download_best_subtitles(self, path, video, lang, min_score):
        logger.debug("_download_best_subtitles(%s, %s, %s, %d)", path, video, lang, min_score)
        subs = self._provider_pool.list_subtitles(video, {lang})
        all_downloaded = self._datastore.get_downloads_for_video(path)
        downloaded = all_downloaded[lang] if lang in downloaded else []
        sub, score = self._find_best_sub(path, video, lang, subs, downloaded)
        if score < min_score:
            return
        self._provider_pool.download_subtitle(sub)
        subtitle_path = subliminal.subtitle.get_subtitle_path(path, language=lang)
        with io.open(subtitle_path, 'wb') as f:
            f.write(sub.content)
        self._datastore.add_download(path, sub.provider_name, str(sub.id), lang, score)

    def check_for_better(self):
        logger.debug("check_for_better()")
        ignore_older_than = datetime.utcnow() - timedelta(days=self._settings.search_for_days)
        incomplete_videos = self._datastore.get_incomplete_videos(
            self._settings.languages, self._settings.desired_movie_score, self._settings.desired_episode_score, ignore_older_than)
        for video in incomplete_videos:
            for need in video['needs']:
                self._download_best_subtitles(video['path'], video['video'], need['lang'], need['current_score'] + 1)

class CoreFactory:
    def __init__(self, settings, db_path):
        self._settings = settings
        self._db_path = db_path

    def get(self):
        return SuperliminalCore(self._settings, self._db_path)
