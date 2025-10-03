# Connection Down Detector

A simple Python tool to continuously monitor connectivity to a predefined list of servers by issuing periodic ICMP pings, displaying a live terminal dashboard (via `rich`) and logging grouped outages (3+ consecutive failures) to a file.

## Features
- Concurrent pings to multiple servers (asyncio)
- Live rich table: latency, success/failure counts, consecutive failures, rolling packet loss %, uptime streak
- Latency classification with emojis:
  - `<60ms` ✅  
  - `60–150ms` ⚠️  
  - `>150ms` 🔴  
  - Timeouts ❌
- Outage grouping: only logs when at least 3 consecutive pings fail; one log line per outage with start/end, duration, missed count
- Rolling packet loss (window size configurable)
- Graceful shutdown with summary

## Requirements
- Python 3.10+
- Linux (focus). On macOS it may still work but options differ; adjust `ping` command if needed.

## Install
```
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run
```
connection-monitor
```
(Or) `python -m connection_monitor.main`

## Configuration
Defaults are in `connection_monitor/config.py`:
- `SERVERS`: list of hosts
- `PING_INTERVAL_SECONDS`: interval per host (default 3s)
- `PING_TIMEOUT_SECONDS`: timeout for a single ping (1s)
- Latency thresholds: `LATENCY_GREEN_MS`, `LATENCY_YELLOW_MS`
- Outage rule: `CONSECUTIVE_FAILURES_FOR_OUTAGE`
- Log file: `LOG_FILE`
- Rolling window size: `ROLLING_WINDOW`
- UI refresh: `UI_REFRESH_INTERVAL`

Modify the file to change behavior; no runtime input needed.

## Log Format
Each outage line: `START -> END | host=HOST missed=N duration=Ds`
If the program stops mid‑outage, it logs a truncated line with the stop time.

## Tests
Run tests with:
```
pytest
```

## Notes
- Running frequent pings may require appropriate permissions depending on system configuration.
- You can add more servers; UI adjusts automatically.

## Future Ideas
- Export metrics via Prometheus
- JSON log option
- Alerting hooks (webhook / email)
