from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

from . import config


@dataclass
class ServerStats:
    host: str
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_rtt_ms: Optional[float] = None
    last_error: Optional[str] = None
    window_results: Deque[bool] = field(
        default_factory=lambda: deque(maxlen=config.ROLLING_WINDOW)
    )
    outage_open: bool = False
    outage_start_ts: Optional[float] = None
    outage_missed: int = 0
    first_success_time: Optional[float] = (
        None  # when we first got success (for uptime streak)
    )
    last_success_time: Optional[float] = None
    uptime_start_time: Optional[float] = (
        None  # start of current uninterrupted success streak
    )
    longest_uptime_streak: float = 0.0
    longest_uptime_streak_ts: Optional[float] = None  # Timestamp of when it ended
    longest_outage_duration: float = 0.0
    longest_outage_ts: Optional[float] = None  # Timestamp of when it ended
    new_longest_uptime_recorded: bool = False

    def record_result(
        self, ok: bool, rtt_ms: Optional[float], error: Optional[str]
    ):
        now = time.time()
        self.new_longest_uptime_recorded = False
        if ok:
            self.success_count += 1
            self.consecutive_failures = 0
            self.last_rtt_ms = rtt_ms
            self.last_error = None
            self.window_results.append(True)
            if self.first_success_time is None:
                self.first_success_time = now
            # Initialize or keep existing uptime streak start
            if self.uptime_start_time is None:
                self.uptime_start_time = now
            self.last_success_time = now
            if self.outage_open:
                # Closing outage handled externally (after calling record_result) to log.
                pass
        else:
            if self.uptime_start_time is not None:
                # An uptime streak just ended
                ended_streak_duration = time.time() - self.uptime_start_time
                if ended_streak_duration > self.longest_uptime_streak:
                    self.longest_uptime_streak = ended_streak_duration
                    self.longest_uptime_streak_ts = time.time()
                    self.new_longest_uptime_recorded = True
            self.failure_count += 1
            self.consecutive_failures += 1
            self.last_rtt_ms = None
            self.last_error = error or "fail"
            self.window_results.append(False)
            # Reset uptime streak start on failure
            self.uptime_start_time = None

    def packet_loss_pct(self) -> float:
        if not self.window_results:
            return 0.0
        failures = sum(1 for r in self.window_results if not r)
        return failures / len(self.window_results) * 100.0

    def classify_latency(self) -> str:
        if self.last_rtt_ms is None:
            return config.EMOJI_TIMEOUT
        if self.last_rtt_ms < config.LATENCY_GREEN_MS:
            return config.EMOJI_GREEN
        if self.last_rtt_ms < config.LATENCY_YELLOW_MS:
            return config.EMOJI_YELLOW
        return config.EMOJI_RED

    def current_uptime_streak(self) -> float:
        """Seconds of continuous success since last failure. 0 if currently failing or no success yet."""
        if self.consecutive_failures > 0:
            return 0.0
        if self.uptime_start_time is None:
            return 0.0
        return time.time() - self.uptime_start_time