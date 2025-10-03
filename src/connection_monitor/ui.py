from __future__ import annotations

from datetime import datetime

from rich import box
from rich.console import Console
from rich.table import Table

from . import config
from .stats import GlobalStats, ServerStats


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    else:
        return f"{seconds / 86400:.1f}d"


def build_table(
    stats_map: dict[str, ServerStats], global_stats: GlobalStats
) -> Table:
    is_all_hosts_down = all(st.consecutive_failures > 0 for st in stats_map.values())

    if is_all_hosts_down:
        status_title = f"[bold red]OFFLINE[/bold red] - Outage for {format_duration(global_stats.get_current_outage_duration())}"
    else:
        status_title = f"[bold green]ONLINE[/bold green] - Uptime for {format_duration(global_stats.get_current_uptime())}"

    table = Table(
        title=f"{status_title}",
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

        table.add_row(
            host,
            status_text,
            rtt_display,
            latency_emoji,
            str(st.success_count),
            str(st.failure_count),
            str(st.consecutive_failures),
            f"{st.packet_loss_pct():.0f}",
        )

    longest_uptime_str = "-"
    if global_stats.longest_uptime_ts:
        longest_uptime_str = (
            f"{format_duration(global_stats.longest_uptime)} (ended on "
            f"{datetime.fromtimestamp(global_stats.longest_uptime_ts).strftime(config.LOG_TIME_FORMAT)})"
        )

    longest_outage_str = "-"
    if global_stats.longest_outage_ts:
        longest_outage_str = (
            f"{format_duration(global_stats.longest_outage)} (ended on "
            f"{datetime.fromtimestamp(global_stats.longest_outage_ts).strftime(config.LOG_TIME_FORMAT)})"
        )

    table.caption = (
        f"Longest Uptime: {longest_uptime_str}\n"
        f"Longest Outage: {longest_outage_str}"
    )

    return table
