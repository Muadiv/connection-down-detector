from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

from . import config


@dataclass
class GlobalStats:
    """Tracks the global state of connectivity across all servers."""

    # Timestamp of when the current continuous uptime streak started.
    # An uptime streak is when at least one server is reachable.
    uptime_start_ts: Optional[float] = None

    # Timestamp of when the current complete outage started.
    # An outage is when all servers are unreachable.
    outage_start_ts: Optional[float] = None

    longest_uptime: float = 0.0
    longest_uptime_ts: Optional[float] = None  # Timestamp of when it ended

    longest_outage: float = 0.0
    longest_outage_ts: Optional[float] = None  # Timestamp of when it ended

    new_longest_uptime_recorded: bool = False
    new_longest_outage_recorded: bool = False

    def get_current_uptime(self) -> float:
        if self.uptime_start_ts is None:
            return 0.0
        return time.time() - self.uptime_start_ts

    def get_current_outage_duration(self) -> float:
        if self.outage_start_ts is None:
            return 0.0
        return time.time() - self.outage_start_ts


@dataclass
class ServerStats:
    """Tracks the statistics for a single server."""

    host: str
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_rtt_ms: Optional[float] = None
    last_error: Optional[str] = None
    window_results: Deque[bool] = field(
        default_factory=lambda: deque(maxlen=config.ROLLING_WINDOW)
    )

    def record_result(
        self, ok: bool, rtt_ms: Optional[float], error: Optional[str]
    ):
        """Record a single ping result for this server."""
        if ok:
            self.success_count += 1
            self.consecutive_failures = 0
            self.last_rtt_ms = rtt_ms
            self.last_error = None
            self.window_results.append(True)
        else:
            self.failure_count += 1
            self.consecutive_failures += 1
            self.last_rtt_ms = None
            self.last_error = error or "fail"
            self.window_results.append(False)

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
