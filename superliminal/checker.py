import logging
from threading import Timer
from core import SuperliminalCore
from . import env

logger = logging.getLogger(__name__)

class Checker:
    def start(self):
        logger.info("Checker thread starting...")
        self._start_timer()

    def _get_interval(self):
        return env.settings.search_interval_hours * 60 * 60

    def _start_timer(self):
        self._timer = Timer(self._get_interval(), self._check)
        self._timer.daemon = True
        self._timer.start()

    def stop(self):
        logger.info("Checker thread stopping...")
        self._timer.cancel();

    def _check(self):
        try:
            logger.info("Initiating check for better subs...")
            SuperliminalCore.check_for_better()
        finally:
            self._start_timer()
