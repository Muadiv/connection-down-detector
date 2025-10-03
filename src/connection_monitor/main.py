from __future__ import annotations

import asyncio
import contextlib
import signal
import sys
import time
from typing import Dict

from rich.console import Console
from rich.live import Live

from . import config
from .outage_logger import OutageLogger
from .ping import ping_host
from .stats import GlobalStats, ServerStats
from .ui import build_table

console = Console()


async def ping_loop(host: str, stats: ServerStats, stop_event: asyncio.Event):
    """Continuously pings a single host and records the results."""
    while not stop_event.is_set():
        start = time.time()
        res = await ping_host(host, config.PING_TIMEOUT_SECONDS)
        stats.record_result(res.ok, res.rtt_ms, res.error)
        await asyncio.sleep(
            max(0, config.PING_INTERVAL_SECONDS - (time.time() - start))
        )


async def stats_aggregator(
    stats_map: Dict[str, ServerStats],
    global_stats: GlobalStats,
    outage_logger: OutageLogger,
    stop_event: asyncio.Event,
):
    """Monitors all servers and updates the global connection state."""
    while not stop_event.is_set():
        now = time.time()
        all_hosts_down = all(s.consecutive_failures > 0 for s in stats_map.values())

        # Uptime tracking
        if all_hosts_down:
            # End of an uptime streak
            if global_stats.uptime_start_ts is not None:
                duration = now - global_stats.uptime_start_ts
                if duration > global_stats.longest_uptime:
                    global_stats.longest_uptime = duration
                    global_stats.longest_uptime_ts = now
                    outage_logger.log_longest_uptime(duration, now)
                global_stats.uptime_start_ts = None
        else:
            # Start of a new uptime streak
            if global_stats.uptime_start_ts is None:
                global_stats.uptime_start_ts = now

        # Outage tracking
        if all_hosts_down:
            # Start of a new outage
            if global_stats.outage_start_ts is None:
                global_stats.outage_start_ts = now
                outage_logger.log_outage_start(now)
        else:
            # End of an outage
            if global_stats.outage_start_ts is not None:
                duration = now - global_stats.outage_start_ts
                outage_logger.log_outage_end(global_stats.outage_start_ts, now)
                if duration > global_stats.longest_outage:
                    global_stats.longest_outage = duration
                    global_stats.longest_outage_ts = now
                    outage_logger.log_longest_outage(duration, now)
                global_stats.outage_start_ts = None

        await asyncio.sleep(0.1)  # High-frequency check


async def ui_loop(
    stats_map: Dict[str, ServerStats],
    global_stats: GlobalStats,
    stop_event: asyncio.Event,
):
    """Renders the live UI table."""
    with Live(
        build_table(stats_map, global_stats),
        refresh_per_second=int(1 / config.UI_REFRESH_INTERVAL),
        console=console,
        screen=False,
    ) as live:
        while not stop_event.is_set():
            live.update(build_table(stats_map, global_stats))
            await asyncio.sleep(config.UI_REFRESH_INTERVAL)


async def main_async():
    """The main asynchronous entry point of the application."""
    stop_event = asyncio.Event()
    stats_map: Dict[str, ServerStats] = {
        h: ServerStats(h) for h in config.SERVERS
    }
    global_stats = GlobalStats()
    outage_logger = OutageLogger(config.LOG_FILE)

    loop = asyncio.get_running_loop()

    def _signal_handler():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:  # Windows
            signal.signal(sig, lambda s, f: _signal_handler())

    # Start all background tasks
    tasks = [
        asyncio.create_task(ping_loop(host, stats, stop_event))
        for host, stats in stats_map.items()
    ]
    tasks.append(
        asyncio.create_task(ui_loop(stats_map, global_stats, stop_event))
    )
    tasks.append(
        asyncio.create_task(
            stats_aggregator(stats_map, global_stats, outage_logger, stop_event)
        )
    )

    await stop_event.wait()

    # Graceful shutdown
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    # Final log entry for any ongoing outage
    if global_stats.outage_start_ts is not None:
        now = time.time()
        outage_logger.log_outage_end(global_stats.outage_start_ts, now)

    # Print summary
    console.print("\nSummary:")
    for h, st in stats_map.items():
        console.print(
            f"{h}: success={st.success_count} fail={st.failure_count} packet_loss={st.packet_loss_pct():.1f}%"
        )


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
