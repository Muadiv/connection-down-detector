from __future__ import annotations

import asyncio
import contextlib
import re
from typing import Optional

PING_RTT_RE = re.compile(r"time=([0-9]*\.?[0-9]+) ms")


class PingResult:
    __slots__ = ("host", "ok", "rtt_ms", "error")

    def __init__(
        self, host: str, ok: bool, rtt_ms: Optional[float], error: Optional[str]
    ):
        self.host = host
        self.ok = ok
        self.rtt_ms = rtt_ms
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"PingResult(host={self.host!r}, ok={self.ok}, rtt_ms={self.rtt_ms}, error={self.error!r})"


async def ping_host(host: str, timeout: float) -> PingResult:
    """Ping a host once using the system 'ping' command (Linux-focused).

    Uses: ping -c 1 -w {timeout} host
    Returns RTT in ms if successful. If timeout or non-zero exit, returns ok=False.
    """
    # -c 1 : send one packet
    # -n   : numeric output (avoid DNS reverse lookups slowing us)
    # -w timeout : total deadline seconds
    proc = await asyncio.create_subprocess_exec(
        "ping",
        "-n",
        "-c",
        "1",
        "-w",
        str(int(timeout)),
        host,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout + 0.5
        )
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        return PingResult(host, False, None, "timeout")

    stdout = out_bytes[0].decode(errors="replace")
    if proc.returncode == 0:
        # Extract RTT
        match = PING_RTT_RE.search(stdout)
        rtt_ms = float(match.group(1)) if match else None
        return PingResult(host, True, rtt_ms, None)
    else:
        # Non-zero exit; attempt to categorize
        err: str = "timeout" if "100% packet loss" in stdout else "unreachable"
        return PingResult(host, False, None, err)
