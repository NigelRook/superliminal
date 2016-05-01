import os
import sys
import logging
from .settings import Settings

logger = logging.getLogger(__name__)

paths = None
settings = None

class Paths(object):
    def __init__(self, data_dir):
        self._data_dir = data_dir

    @property
    def data_dir(self):
        return self._data_dir

    @property
    def logs_dir(self):
        return os.path.join(self._data_dir, 'logs/')

    @property
    def log_file(self):
        return os.path.join(self.logs_dir, 'superliminal.log')

    @property
    def db_path(self):
        return os.path.join(self._data_dir, 'db/')

    @property
    def cache_file(self):
        return os.path.join(self._data_dir, 'subliminal.dbm')


def get_default_data_dir():
    # Windows
    if os.name == 'nt':
        return os.path.join(os.environ['APPDATA'], 'Superliminal')

    try:
        import pwd
        if not os.environ['HOME']:
            os.environ['HOME'] = sp(pwd.getpwuid(os.geteuid()).pw_dir)
    except:
        pass

    user_dir = os.path.expanduser('~')

    # OSX
    import platform
    if 'darwin' in platform.platform().lower():
        return os.path.join(user_dir, 'Library', 'Application Support', 'Superliminal')

    # FreeBSD
    if 'freebsd' in sys.platform:
        return os.path.join('/usr/local/', 'superliminal', 'data')

    # Linux
    return os.path.join(user_dir, '.superliminal')

def load(data_dir=None, config_file=None):
    global paths, settings
    data_dir = data_dir or get_default_data_dir()
    paths = Paths(data_dir)
    logger.info("Db at '%s'", paths.db_path)

    config_file = config_file or os.path.join(data_dir, 'superliminal.cfg')
    logger.info("Loading settings from '%s'", config_file)
    settings = Settings(config_file)
