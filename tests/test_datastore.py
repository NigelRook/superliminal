import pytest
import tempfile
from subliminal.video import Video
from babelfish import Language
from datetime import datetime, timedelta

import superliminal.datastore

class DatastoreFixture:
    def __init__(self):
        self.db_file = tempfile.NamedTemporaryFile()
        self.db_path = self.db_file.name

    def finalize(self):
        self.db_file.close()

@pytest.fixture
def fixture(request):
    f = DatastoreFixture()
    request.addfinalizer(f.finalize)
    return f

def test_newly_added_video_has_no_downloads(fixture):
    datastore = superliminal.datastore.SqLiteDataStore(fixture.db_path)
    path = "/data/Series/Season 1/01 Title.mkv"
    video = Video.fromname("Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv")
    datastore.add_video(path, video)

    downloads = datastore.get_downloads_for_video(path)

    assert downloads == {}

def test_added_sub_is_returned(fixture):
    datastore = superliminal.datastore.SqLiteDataStore(fixture.db_path)
    path = "/data/Series/Season 1/01 Title.mkv"
    video = Video.fromname("Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv")
    datastore.add_video(path, video)
    provider = "davessubs"; sub_id = "ABC123"; lang = Language.fromietf('en'); score = 123
    datastore.add_download(path, provider, sub_id, lang, score)

    downloads = datastore.get_downloads_for_video(path)

    assert downloads == {lang: [{'provider': provider, 'sub_id': sub_id, 'lang': lang, 'score': score}]}

def test_added_subs_are_returned_by_lang(fixture):
    datastore = superliminal.datastore.SqLiteDataStore(fixture.db_path)
    path = "/data/Series/Season 1/01 Title.mkv"
    video = Video.fromname("Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv")
    datastore.add_video(path, video)

    provider1 = "davessubs"; sub_id1 = "ABC123"; lang1 = Language.fromietf('en'); score1 = 123
    provider2 = "stevesubs"; sub_id2 = "steve123"; lang2 = lang1; score2 = 120
    provider3 = "pablosubs"; sub_id3 = "umdoistres"; lang3 = Language.fromietf('pt-BR'); score3 = 150
    datastore.add_download(path, provider1, sub_id1, lang1, score1)
    datastore.add_download(path, provider2, sub_id2, lang2, score2)
    datastore.add_download(path, provider3, sub_id3, lang3, score3)

    downloads = datastore.get_downloads_for_video(path)

    assert downloads == {lang1: [{'provider': provider1, 'sub_id': sub_id1, 'lang': lang1, 'score': score1},
                                 {'provider': provider2, 'sub_id': sub_id2, 'lang': lang2, 'score': score2}],
                         lang3: [{'provider': provider3, 'sub_id': sub_id3, 'lang': lang3, 'score': score3}]}

def test_replacing_video_for_path_removes_downloads(fixture):
    datastore = superliminal.datastore.SqLiteDataStore(fixture.db_path)
    path = "/data/Series/Season 1/01 Title.mkv"
    video = Video.fromname("Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv")
    datastore.add_video(path, video)
    provider = "davessubs"; sub_id = "ABC123"; lang = Language.fromietf('en'); score = 123
    datastore.add_download(path, provider, sub_id, lang, score)

    video2 = Video.fromname("Series.S01E02.Title.720p.BDRip-ReleaseGroup2.mkv")
    datastore.add_video(path, video)
    downloads = datastore.get_downloads_for_video(path)

    assert downloads == {}

def test_get_incomplete_videos_returns_nothing_when_no_videos_exist(fixture):
    datastore = superliminal.datastore.SqLiteDataStore(fixture.db_path)

    lang = Language.fromietf('en')
    incomplete = datastore.get_incomplete_videos([lang], 100, 100, datetime.utcnow()- timedelta(days=1))

get_incomplete_videos_scenarios = [
    {'name':'no videos returns empty',
     'videos':[],
     'expected':[]},
    {'name':'video with no downloads returns all languages',
     'videos':[{'path':"/data/Series/Season 1/02 Title.mkv",
                'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
                'downloads':[]}],
     'expected':[(0, [('en', 0), ('pt-BR', 0)])]},
    {'name':'excludes languages with downloads >= desired',
     'videos':[{'path':"/data/Series/Season 1/02 Title.mkv",
                'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
                'downloads':[('davesubs', 'ds123', 'en', 100)]}],
     'expected':[(0, [('pt-BR', 0)])]},
    {'name':'excludes video when all languages have downloads >= desired',
     'videos':[{'path':"/data/Series/Season 1/02 Title.mkv",
                'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
                'downloads':[('davesubs', 'ds123', 'en', 100),
                             ('pablosubs', 'ps16', 'pt-BR', 123)]}],
     'expected':[]},
    {'name':'includes languages with downloads < desired',
     'videos':[{'path':"/data/Series/Season 1/02 Title.mkv",
                'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
                'downloads':[('davesubs', 'ds123', 'en', 100),
                             ('pablosubs', 'ps16', 'pt-BR', 80)]}],
     'expected':[(0, [('pt-BR', 80)])]},
    {'name':'returns highest score for language when multiple downloads found',
     'videos':[{'path':"/data/Series/Season 1/02 Title.mkv",
                'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
                'downloads':[('davesubs', 'ds123', 'en', 100),
                             ('pablosubs', 'ps16', 'pt-BR', 83),
                             ('pablosubs', 'ps22', 'pt-BR', 80)]}],
     'expected':[(0, [('pt-BR', 83)])]},
    {'name':'excludes language if any score >= desired',
     'videos':[{'path':"/data/Series/Season 1/02 Title.mkv",
                'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
                'downloads':[('davesubs', 'ds123', 'en', 100),
                             ('stevesubs', 'steve69', 'en', 83),
                             ('pablosubs', 'ps22', 'pt-BR', 80)]}],
     'expected':[(0, [('pt-BR', 80)])]},
    {'name':'uses different desired score for movies',
     'videos':[{'path':"/data/Title (2016)/Title.mkv",
                'name':"Title.2016.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
                'downloads':[('davesubs', 'ds123', 'en', 80),
                             ('pablosubs', 'ps16', 'pt-BR', 79)]}],
     'expected':[(0, [('pt-BR', 79)])]},
    {'name':'returns multiple videos',
     'videos':[{'path':"/data/Series/Season 1/02 Title.mkv",
                'name':"Series.S01E02.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
                'downloads':[('pablosubs', 'ps16', 'pt-BR', 80)]},
               {'path':"/data/Series/Season 1/03 Title.mkv",
                'name':"Series.S01E03.Title.720p.WEB-DL.DD5.1.H264-ReleaseGroup.mkv",
                'downloads':[('davesubs', 'ds123', 'en', 100)]}],
     'expected':[(0, [('en', 0), ('pt-BR', 80)]),
                 (1, [('pt-BR', 0)])]}
]

@pytest.mark.parametrize("scenario", get_incomplete_videos_scenarios, ids=lambda scenario:scenario['name'])
def test_get_incomplete_videos(fixture, scenario):
    datastore = superliminal.datastore.SqLiteDataStore(fixture.db_path)
    for video in scenario['videos']:
        datastore.add_video(video['path'], Video.fromname(video['name']))
        for provider, sub_id, lang, score in video['downloads']:
            datastore.add_download(video['path'], provider, sub_id, Language.fromietf(lang), score)

    lang1 = Language.fromietf('en'); lang2 = Language.fromietf('pt-BR')
    incomplete = datastore.get_incomplete_videos([lang1, lang2], 80, 100, datetime.utcnow() - timedelta(days=1))

    assert len(incomplete) == len(scenario['expected'])
    for video_idx, needs in scenario['expected']:
        actual = next(video for video in incomplete if video['path'] == scenario['videos'][video_idx]['path'])
        assert actual['video'].name == scenario['videos'][video_idx]['name']
        assert len(actual['needs']) == len(needs)
        for lang, score in needs:
            actual_need = next(need for need in actual['needs'] if str(need['lang']) == lang)
            assert actual_need['current_score'] == score
