#!/usr/bin/env python
import os
import sys
import logging
from datetime import timedelta

from argparse import ArgumentParser

base_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(base_path, 'libs'))

from superliminal.checker import Checker
from superliminal.settings import Settings
from superliminal.core import CoreFactory
import superliminal.api

logger = logging.getLogger(__name__)

def get_data_dir():

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


def get_opts(args):
    parser = ArgumentParser(prog = 'superliminalpy')
    parser.add_argument('--data_dir',
                        dest = 'data_dir', help = 'Absolute or ~/ path of the data dir')
    parser.add_argument('--config_file',
                        dest = 'config_file', help = 'Absolute or ~/ path of the settings file (default DATA_DIR/settings.conf)')
    parser.add_argument('--debug', action = 'store_true',
                        dest = 'debug', help = 'Debug mode')

    opts = parser.parse_args(args)

    if not opts.data_dir:
        opts.data_dir = get_data_dir()

    if not opts.config_file:
        opts.config_file = os.path.join(opts.data_dir, 'superliminal.cfg')

    return opts

def init_logging(filename, level):
    logger = logging.getLogger()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setFormatter(formatter)

    logger.addHandler(ch)

    fh = logging.handlers.TimedRotatingFileHandler(filename=filename, when='W0', interval=1, backupCount=5)
    fh.setFormatter(formatter)

    logger.addHandler(fh)

    logger.setLevel(level)

    # Don't want debug logging from everyone
    for logger_name in ['guessit', 'subliminal', 'tornado', 'stevedore']:
        logging.getLogger(logger_name).setLevel(logging.INFO)

if __name__ == '__main__':
    opts = get_opts(sys.argv[1:])

    if not os.path.isdir(opts.data_dir):
        os.makedirs(opts.data_dir)

    logs_dir = os.path.join(opts.data_dir, 'logs/')
    if not os.path.isdir(logs_dir):
        os.makedirs(logs_dir)

    logfile = os.path.join(logs_dir, 'superliminal.log')

    init_logging(logfile, logging.DEBUG)

    logger.info("Starting up...")

    db_path = os.path.join(opts.data_dir, 'superliminal.db')
    subliminal_cache_path = os.path.join(opts.data_dir, 'subliminal.dbm')

    logger.info("Loading settings from '%s'", opts.config_file)
    settings = Settings(opts.config_file)

    logger.info("subliminal cache at '%s'", subliminal_cache_path)
    from subliminal.cache import region
    region.configure('dogpile.cache.dbm', expiration_time=timedelta(days=30),
                     arguments={'filename': subliminal_cache_path})

    logger.info("Db at '%s'", db_path)
    core_factory = CoreFactory(settings, db_path)

    logger.info("Running startup check for better subs...")
    with core_factory.get() as c:
        c.check_for_better()

    logger.info("Starting periodic better subs checking thread...")
    checker = Checker(settings, core_factory)
    checker.start()

    try:
        superliminal.api.run(core_factory)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        pass
