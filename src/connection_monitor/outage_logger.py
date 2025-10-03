from __future__ import annotations

import time
from datetime import datetime
from typing import TextIO

from . import config
from .stats import ServerStats


class OutageLogger:
    def __init__(self, path: str):
        self.path = path

    def _open(self) -> TextIO:
        return open(self.path, "a", encoding="utf-8")

    def log_outage(
        self, host: str, start_ts: float, end_ts: float, missed: int
    ):
        start_str = datetime.fromtimestamp(start_ts).strftime(
            config.LOG_TIME_FORMAT
        )
        end_str = datetime.fromtimestamp(end_ts).strftime(
            config.LOG_TIME_FORMAT
        )
        duration = end_ts - start_ts
        line = f"{start_str} -> {end_str} | host={host} missed={missed} duration={duration:.1f}s\n"
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
            self.log_outage(
                stats.host,
                stats.outage_start_ts or end_ts,
                end_ts,
                stats.outage_missed,
            )
            stats.outage_open = False
            stats.outage_start_ts = None
            stats.outage_missed = 0

    def finalize(self, stats_list):
        now = time.time()
        for s in stats_list:
            if s.outage_open:
                # log truncated outage on shutdown
                self.log_outage(
                    s.host, s.outage_start_ts or now, now, s.outage_missed
                )
                # log truncated outage on shutdown
                self.log_outage(
                    s.host, s.outage_start_ts or now, now, s.outage_missed
                )
