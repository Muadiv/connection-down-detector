from __future__ import annotations

import os
import time
from datetime import datetime
from typing import TextIO

from . import config


class OutageLogger:
    def __init__(self, path: str):
        self.path = path

    def _open(self) -> TextIO:
        self._maybe_rotate_log()
        return open(self.path, "a", encoding="utf-8")

    def log_outage_start(self, ts: float):
        ts_str = datetime.fromtimestamp(ts).strftime(config.LOG_TIME_FORMAT)
        line = f"{ts_str} | GLOBAL_OUTAGE_START\n"
        with self._open() as f:
            f.write(line)

    def log_outage_end(self, start_ts: float, end_ts: float):
        start_str = datetime.fromtimestamp(start_ts).strftime(
            config.LOG_TIME_FORMAT
        )
        end_str = datetime.fromtimestamp(end_ts).strftime(config.LOG_TIME_FORMAT)
        duration = end_ts - start_ts
        line = f"{start_str} -> {end_str} | GLOBAL_OUTAGE_END duration={duration:.1f}s\n"
        with self._open() as f:
            f.write(line)

    def log_longest_uptime(self, duration: float, ts: float):
        ts_str = datetime.fromtimestamp(ts).strftime(config.LOG_TIME_FORMAT)
        line = f"{ts_str} | NEW_LONGEST_UPTIME duration={duration:.1f}s\n"
        with self._open() as f:
            f.write(line)

    def log_longest_outage(self, duration: float, ts: float):
        ts_str = datetime.fromtimestamp(ts).strftime(config.LOG_TIME_FORMAT)
        line = f"{ts_str} | NEW_LONGEST_OUTAGE duration={duration:.1f}s\n"
        with self._open() as f:
            f.write(line)

    def _maybe_rotate_log(self):
        # Rotate log if it's been more than 90 days since last modification
        try:
            last_mod_time = os.path.getmtime(self.path)
            if time.time() - last_mod_time > 90 * 24 * 60 * 60:
                # create a new name with timestamp
                new_name = self.path + "." + datetime.fromtimestamp(last_mod_time).strftime("%Y%m%d%H%M%S")
                os.rename(self.path, new_name)
        except FileNotFoundError:
            pass  # file doesn't exist yet, that's ok
