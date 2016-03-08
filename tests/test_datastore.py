import pytest
import tempfile
from subliminal.video import Video

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

    assert downloads == []
