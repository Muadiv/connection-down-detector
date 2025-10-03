from __future__ import annotations

# Predefined server list (hostnames or IPs)
SERVERS: list[str] = [
    "8.8.8.8",  # Google DNS
    "1.1.1.1",  # Cloudflare DNS
    "9.9.9.9",  # Quad9 DNS
    "github.com",
    "aws.amazon.com",
]

# Ping settings
PING_INTERVAL_SECONDS = 3.0  # how often each server is pinged
PING_TIMEOUT_SECONDS = 1.0  # fail if no reply within this time

# Latency classification thresholds (ms)
LATENCY_GREEN_MS = 60
LATENCY_YELLOW_MS = 150

# Outage detection
CONSECUTIVE_FAILURES_FOR_OUTAGE = 3

# Logging
LOG_FILE = "connection_down.log"
LOG_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Rolling window size for packet loss percentage (per server)
ROLLING_WINDOW = 50

# Table refresh rate (seconds) - can be faster than ping interval to feel responsive
UI_REFRESH_INTERVAL = 0.5

# Emoji/status mapping
EMOJI_GREEN = "✅"
EMOJI_YELLOW = "⚠️"
EMOJI_RED = "🔴"
EMOJI_TIMEOUT = "❌"
