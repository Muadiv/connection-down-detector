from __future__ import annotations

import time
from datetime import datetime

from rich import box
from rich.console import Console
from rich.live import Live
from rich.table import Table

from . import config
from .stats import ServerStats

console = Console()


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    else:
        return f"{seconds / 86400:.1f}d"


def build_table(stats_map: dict[str, ServerStats]) -> Table:
    table = Table(
        title="Connection Monitor",
        box=box.MINIMAL_DOUBLE_HEAD,
        expand=True,
        caption_style="bold",
    )
    table.add_column("Host", style="bold")
    table.add_column("Status")
    table.add_column("RTT (ms)")
    table.add_column("Latency")
    table.add_column("Success")
    table.add_column("Fail")
    table.add_column("Consec Fail")
    table.add_column("Packet Loss %")
    table.add_column("Uptime Streak")

    longest_uptime_host = "-"
    longest_uptime_str = "-"
    longest_outage_host = "-"
    longest_outage_str = "-"

    max_uptime = 0.0
    max_outage = 0.0

    for host, st in stats_map.items():
        if st.last_rtt_ms is not None:
            rtt_display = f"{st.last_rtt_ms:.1f}"
        else:
            rtt_display = "-"
        latency_emoji = st.classify_latency()
        status_text = (
            "OK"
            if st.consecutive_failures == 0
            else f"DOWN ({st.consecutive_failures})"
        )
        if st.outage_open:
            status_text = (
                "OUTAGE"
                if st.consecutive_failures
                >= config.CONSECUTIVE_FAILURES_FOR_OUTAGE
                else status_text
            )
        loss = st.packet_loss_pct()
        uptime = st.current_uptime_streak()
        uptime_str = format_duration(uptime) if uptime >= 1 else "-"
        table.add_row(
            host,
            status_text,
            rtt_display,
            latency_emoji,
            str(st.success_count),
            str(st.failure_count),
            str(st.consecutive_failures),
            f"{loss:.0f}",
            uptime_str,
        )
        if st.longest_uptime_streak > max_uptime:
            max_uptime = st.longest_uptime_streak
            longest_uptime_host = host
            longest_uptime_str = (
                f"{format_duration(st.longest_uptime_streak)} (ended on "
                f"{datetime.fromtimestamp(st.longest_uptime_streak_ts).strftime(config.LOG_TIME_FORMAT)})"
            )

        if st.longest_outage_duration > max_outage:
            max_outage = st.longest_outage_duration
            longest_outage_host = host
            longest_outage_str = (
                f"{format_duration(st.longest_outage_duration)} (ended on "
                f"{datetime.fromtimestamp(st.longest_outage_ts).strftime(config.LOG_TIME_FORMAT)})"
            )

    table.caption = (
        f"Longest Uptime: {longest_uptime_str} (host: {longest_uptime_host})\n"
        f"Longest Outage: {longest_outage_str} (host: {longest_outage_host})"
    )

    return table
