import os
import sys
import logging
from datetime import timedelta
from argparse import ArgumentParser
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer

from .settings import Settings
from .core import SuperliminalCore
from . import api, env

logger = logging.getLogger(__name__)

def get_opts(args):
    parser = ArgumentParser(prog = 'superliminalpy')
    parser.add_argument('--data_dir',
                        dest = 'data_dir', help = 'Absolute or ~/ path of the data dir')
    parser.add_argument('--config_file',
                        dest = 'config_file', help = 'Absolute or ~/ path of the settings file (default DATA_DIR/settings.conf)')
    parser.add_argument('--debug', action = 'store_true',
                        dest = 'debug', help = 'Debug mode')

    return parser.parse_args(args)

def init_logging(level):
    logger = logging.getLogger()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.setLevel(level)

    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    fh = logging.handlers.TimedRotatingFileHandler(filename=env.paths.log_file, when='W0', interval=1, backupCount=5)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Don't want debug logging from everyone
    for logger_name in ['guessit', 'tornado', 'stevedore', 'rebulk', 'dogpile']:
        logging.getLogger(logger_name).setLevel(logging.INFO)

@gen.coroutine
def check_for_better():
    while True:
        yield gen.sleep(env.settings.search_interval_hours * 60 * 60)
        try:
            logger.info("Initiating check for better subs...")
            SuperliminalCore.check_for_better()
        except:
            logger.exception("Error in check for better")

def run_server():
    application = api.create_application()
    http_server = HTTPServer(application)
    http_server.listen(5000)
    try:
        SuperliminalCore.start_consumer()
        IOLoop.current().start()
    finally:
        http_server.stop()

def run(args):
    opts = get_opts(args)

    env.load(data_dir = opts.data_dir, config_file = opts.config_file)

    if not os.path.isdir(env.paths.data_dir):
        os.makedirs(env.paths.data_dir)

    if not os.path.isdir(env.paths.logs_dir):
        os.makedirs(env.paths.logs_dir)

    init_logging(logging.DEBUG)

    logger.info("Starting up...")

    logger.info("subliminal cache at '%s'", env.paths.cache_file)
    from subliminal.cache import region
    region.configure('dogpile.cache.dbm', expiration_time=timedelta(days=30),
                     arguments={'filename': env.paths.cache_file})

    logger.info("Spawning check_for_better async loop")
    IOLoop.current().spawn_callback(check_for_better)

    try:
        run_server()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        pass
