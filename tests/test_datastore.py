import pytest
import tempfile
from subliminal.video import Video
from babelfish import Language

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
