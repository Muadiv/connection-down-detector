from __future__ import annotations

import time

from rich import box
from rich.console import Console
from rich.live import Live
from rich.table import Table

from . import config
from .stats import ServerStats

console = Console()


def build_table(stats_map: dict[str, ServerStats]) -> Table:
    table = Table(
        title="Connection Monitor", box=box.MINIMAL_DOUBLE_HEAD, expand=True
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

    now = time.time()
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
        uptime_str = f"{uptime:.0f}s" if uptime >= 1 else "-"
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
    return table


class LiveUI:
    def __init__(self, stats_map: dict[str, ServerStats]):
        self.stats_map = stats_map

    def run(self):
        with Live(
            refresh_per_second=int(1 / config.UI_REFRESH_INTERVAL),
            console=console,
            screen=False,
        ) as live:
            while True:
                live.update(build_table(self.stats_map))
                time.sleep(config.UI_REFRESH_INTERVAL)
