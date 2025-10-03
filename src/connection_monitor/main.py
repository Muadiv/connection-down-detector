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
from .stats import ServerStats
from .ui import build_table

console = Console()


async def ping_loop(host: str, stats: ServerStats, stop_event: asyncio.Event):
    while not stop_event.is_set():
        start = time.time()
        res = await ping_host(host, config.PING_TIMEOUT_SECONDS)
        stats.record_result(res.ok, res.rtt_ms, res.error)
        # Outage tracking handled externally
        await asyncio.sleep(
            max(0, config.PING_INTERVAL_SECONDS - (time.time() - start))
        )


async def manage_stats(
    stats_map: Dict[str, ServerStats],
    outage_logger: OutageLogger,
    stop_event: asyncio.Event,
):
    while not stop_event.is_set():
        for s in stats_map.values():
            if s.consecutive_failures >= config.CONSECUTIVE_FAILURES_FOR_OUTAGE:
                outage_logger.maybe_open_outage(s)
            if s.outage_open and s.consecutive_failures == 0:
                outage_logger.maybe_close_outage(s)
            if s.new_longest_uptime_recorded:
                outage_logger.log_longest_uptime(
                    s.host, s.longest_uptime_streak, s.longest_uptime_streak_ts
                )

        await asyncio.sleep(0.2)


async def ui_loop(stats_map: Dict[str, ServerStats], stop_event: asyncio.Event):
    from rich import box

    with Live(
        build_table(stats_map),
        refresh_per_second=int(1 / config.UI_REFRESH_INTERVAL),
        console=console,
        screen=False,
    ) as live:
        while not stop_event.is_set():
            live.update(build_table(stats_map))
            await asyncio.sleep(config.UI_REFRESH_INTERVAL)


async def main_async():
    stop_event = asyncio.Event()
    stats_map: Dict[str, ServerStats] = {
        h: ServerStats(h) for h in config.SERVERS
    }
    outage_logger = OutageLogger(config.LOG_FILE)

    loop = asyncio.get_running_loop()

    def _signal_handler():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:  # Windows
            signal.signal(sig, lambda s, f: _signal_handler())

    tasks = [
        asyncio.create_task(ping_loop(host, stats_map[host], stop_event))
        for host in config.SERVERS
    ]
    tasks.append(asyncio.create_task(ui_loop(stats_map, stop_event)))
    tasks.append(
        asyncio.create_task(manage_stats(stats_map, outage_logger, stop_event))
    )

    await stop_event.wait()
    # Cancel tasks except ourselves
    for t in tasks:
        t.cancel()
    for t in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await t

    # Finalize outages
    outage_logger.finalize(stats_map.values())

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
