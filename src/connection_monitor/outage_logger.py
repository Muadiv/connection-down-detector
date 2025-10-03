from __future__ import annotations

import os
import time
from datetime import datetime
from typing import TextIO

from . import config
from .stats import ServerStats


class OutageLogger:
    def __init__(self, path: str):
        self.path = path

    def _open(self) -> TextIO:
        self._maybe_rotate_log()
        return open(self.path, "a", encoding="utf-8")

    def log_outage(
        self, host: str, start_ts: float, end_ts: float, missed: int
    ):
        start_str = datetime.fromtimestamp(start_ts).strftime(
            config.LOG_TIME_FORMAT
        )
        end_str = datetime.fromtimestamp(end_ts).strftime(config.LOG_TIME_FORMAT)
        duration = end_ts - start_ts
        line = f"{start_str} -> {end_str} | OUTAGE host={host} missed={missed} duration={duration:.1f}s\n"
        with self._open() as f:
            f.write(line)

    def log_longest_uptime(self, host: str, duration: float, ts: float):
        ts_str = datetime.fromtimestamp(ts).strftime(config.LOG_TIME_FORMAT)
        line = f"{ts_str} | LONGEST_UPTIME host={host} duration={duration:.1f}s\n"
        with self._open() as f:
            f.write(line)

    def log_longest_outage(self, host: str, duration: float, ts: float):
        ts_str = datetime.fromtimestamp(ts).strftime(config.LOG_TIME_FORMAT)
        line = f"{ts_str} | LONGEST_OUTAGE host={host} duration={duration:.1f}s\n"
        with self._open() as f:
            f.write(line)

    def maybe_open_outage(self, stats: ServerStats):
        if (
            not stats.outage_open
            and stats.consecutive_failures
            >= config.CONSECUTIVE_FAILURES_FOR_OUTAGE
        ):
            stats.outage_open = True
            stats.outage_start_ts = time.time()
            stats.outage_missed = stats.consecutive_failures

    def maybe_close_outage(self, stats: ServerStats):
        if stats.outage_open and stats.consecutive_failures == 0:
            # success arrived
            end_ts = time.time()
            start_ts = stats.outage_start_ts or end_ts
            self.log_outage(
                stats.host,
                start_ts,
                end_ts,
                stats.outage_missed,
            )
            duration = end_ts - start_ts
            if duration > stats.longest_outage_duration:
                stats.longest_outage_duration = duration
                stats.longest_outage_ts = end_ts
                self.log_longest_outage(stats.host, duration, end_ts)

            stats.outage_open = False
            stats.outage_start_ts = None
            stats.outage_missed = 0

    def _maybe_rotate_log(self):
        # Rotate log if it's been more than 90 days since last modification
        try:
            last_mod_time = os.path.getmtime(self.path)
            if time.time() - last_mod_time > 90 * 24 * 60 * 60:
                # create a new name with timestamp
                new_name = self.path + "." + datetime.fromtimestamp(last_mod_time).strftime("%Y%m%d%H%M%S")
                os.rename(self.path, new_name)
        except FileNotFoundError:
            pass # file doesn't exist yet, that's ok

    def finalize(self, stats_list):
        now = time.time()
        for s in stats_list:
            if s.outage_open:
                # log truncated outage on shutdown
                self.log_outage(
                    s.host, s.outage_start_ts or now, now, s.outage_missed
                )
