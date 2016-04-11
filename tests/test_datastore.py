import setpaths
import pytest
import tempfile
from subliminal.video import Video
from babelfish import Language
from datetime import datetime, timedelta

from superliminal.datastore import SqLiteDataStore

from unittest import TestCase
from nose_parameterized import parameterized

class DataStoreTests(TestCase):
    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile()
        self.datastore = SqLiteDataStore(self.db_file.name)

    def tearDown(self):
        self.datastore.close()
        self.db_file.close()

    def test_newly_added_video_has_no_downloads(self):
        path = "/data/Series/Season 1/01 Title.mkv"
        video = Video.fromname("Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv")
        self.datastore.add_video(path, video)

        downloads = self.datastore.get_downloads_for_video(path)

        self.assertEqual(downloads, {})

    def test_added_sub_is_returned(self):
        path = "/data/Series/Season 1/01 Title.mkv"
        video = Video.fromname("Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv")
        self.datastore.add_video(path, video)
        provider = "davessubs"; sub_id = "ABC123"; lang = Language.fromietf('en'); score = 123
        self.datastore.add_download(path, provider, sub_id, lang, score)

        downloads = self.datastore.get_downloads_for_video(path)

        self.assertEqual(downloads, {lang: [{'provider': provider, 'sub_id': sub_id, 'lang': lang, 'score': score}]})

    def test_added_subs_are_returned_by_lang(self):
        path = "/data/Series/Season 1/01 Title.mkv"
        video = Video.fromname("Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv")
        self.datastore.add_video(path, video)

        provider1 = "davessubs"; sub_id1 = "ABC123"; lang1 = Language.fromietf('en'); score1 = 123
        provider2 = "stevesubs"; sub_id2 = "steve123"; lang2 = lang1; score2 = 120
        provider3 = "pablosubs"; sub_id3 = "umdoistres"; lang3 = Language.fromietf('pt-BR'); score3 = 150
        self.datastore.add_download(path, provider1, sub_id1, lang1, score1)
        self.datastore.add_download(path, provider2, sub_id2, lang2, score2)
        self.datastore.add_download(path, provider3, sub_id3, lang3, score3)

        downloads = self.datastore.get_downloads_for_video(path)

        self.assertEqual(downloads, {lang1: [{'provider': provider1, 'sub_id': sub_id1, 'lang': lang1, 'score': score1},
                                             {'provider': provider2, 'sub_id': sub_id2, 'lang': lang2, 'score': score2}],
                                     lang3: [{'provider': provider3, 'sub_id': sub_id3, 'lang': lang3, 'score': score3}]})

    def test_replacing_video_for_path_removes_downloads(self):
        path = "/data/Series/Season 1/01 Title.mkv"
        video = Video.fromname("Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv")
        self.datastore.add_video(path, video)
        provider = "davessubs"; sub_id = "ABC123"; lang = Language.fromietf('en'); score = 123
        self.datastore.add_download(path, provider, sub_id, lang, score)

        video2 = Video.fromname("Series.S01E02.Title.720p.BDRip-ReleaseGroup2.mkv")
        self.datastore.add_video(path, video)
        downloads = self.datastore.get_downloads_for_video(path)

        self.assertEqual(downloads, {})

    def test_get_incomplete_videos_returns_nothing_when_no_videos_exist(self):
        lang = Language.fromietf('en')
        incomplete = self.datastore.get_incomplete_videos([lang], 100, 100, datetime.utcnow()- timedelta(days=1))

    @parameterized.expand([
        ('no videos returns empty', [], []),
        ('video with no downloads returns all languages',
         [{'path':"/data/Series/Season 1/02 Title.mkv",
           'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[]}],
         [(0, [('en', 0), ('pt-BR', 0)])]),
        ('excludes languages with downloads >= desired',
         [{'path':"/data/Series/Season 1/02 Title.mkv",
           'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[('davesubs', 'ds123', 'en', 100)]}],
         [(0, [('pt-BR', 0)])]),
        ('excludes video when all languages have downloads >= desired',
         [{'path':"/data/Series/Season 1/02 Title.mkv",
           'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[('davesubs', 'ds123', 'en', 100),
                        ('pablosubs', 'ps16', 'pt-BR', 123)]}],
         []),
        ('includes languages with downloads < desired',
         [{'path':"/data/Series/Season 1/02 Title.mkv",
           'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[('davesubs', 'ds123', 'en', 100),
                        ('pablosubs', 'ps16', 'pt-BR', 80)]}],
         [(0, [('pt-BR', 80)])]),
        ('returns highest score for language when multiple downloads found',
         [{'path':"/data/Series/Season 1/02 Title.mkv",
           'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[('davesubs', 'ds123', 'en', 100),
                        ('pablosubs', 'ps16', 'pt-BR', 83),
                        ('pablosubs', 'ps22', 'pt-BR', 80)]}],
         [(0, [('pt-BR', 83)])]),
        ('excludes language if any score >= desired',
         [{'path':"/data/Series/Season 1/02 Title.mkv",
           'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[('davesubs', 'ds123', 'en', 100),
                        ('stevesubs', 'steve69', 'en', 83),
                        ('pablosubs', 'ps22', 'pt-BR', 80)]}],
         [(0, [('pt-BR', 80)])]),
        ('uses different desired score for movies',
         [{'path':"/data/Title (2016)/Title.mkv",
           'name':"Title.2016.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[('davesubs', 'ds123', 'en', 80),
                        ('pablosubs', 'ps16', 'pt-BR', 79)]}],
         [(0, [('pt-BR', 79)])]),
        ('returns multiple videos',
         [{'path':"/data/Series/Season 1/02 Title.mkv",
           'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[('pablosubs', 'ps16', 'pt-BR', 80)]},
          {'path':"/data/Series/Season 1/03 Title.mkv",
           'name':"Series.S01E03.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[('davesubs', 'ds123', 'en', 100)]}],
         [(0, [('en', 0), ('pt-BR', 80)]),
          (1, [('pt-BR', 0)])]),
        ('returns multiple videos',
         [{'path':"/data/Series/Season 1/02 Title.mkv",
           'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[],
           'age':timedelta(days=2)},
          {'path':"/data/Series/Season 1/03 Title.mkv",
           'name':"Series.S01E03.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[('davesubs', 'ds123', 'en', 80)],
           'age':timedelta(days=2)},
          {'path':"/data/Series/Season 1/03 Title.mkv",
           'name':"Series.S01E03.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
           'downloads':[],
           'age':timedelta(hours=23)}],
         [(2, [('en', 0), ('pt-BR', 0)])])
    ], testcase_func_name=lambda func, num, param: '%s_%s'%(
        func.__name__, parameterized.to_safe_name(param.args[0])
    ))
    def test_get_incomplete_videos(self, name, videos, expected):
        for video in videos:
            added = datetime.utcnow() - video['age'] if 'age' in video else timedelta(0)
            self.datastore.add_video(video['path'], Video.fromname(video['name']), added)
            for provider, sub_id, lang, score in video['downloads']:
                self.datastore.add_download(video['path'], provider, sub_id, Language.fromietf(lang), score)

        lang1 = Language.fromietf('en'); lang2 = Language.fromietf('pt-BR')
        incomplete = self.datastore.get_incomplete_videos([lang1, lang2], 80, 100, datetime.utcnow() - timedelta(days=1))

        self.assertEqual(len(incomplete), len(expected))
        for video_idx, needs in expected:
            actual = next(video for video in incomplete if video['path'] == videos[video_idx]['path'])
            self.assertEqual(actual['video'].name, videos[video_idx]['name'])
            self.assertEqual(len(actual['needs']), len(needs))
            for lang, score in needs:
                actual_need = next(need for need in actual['needs'] if str(need['lang']) == lang)
                self.assertEqual(actual_need['current_score'], score)
