#!/usr/bin/env python3
"""
Connection Down Detector
Monitor connectivity to multiple servers with live dashboard and outage logging.
"""

import asyncio
import time
import subprocess
import re
from datetime import datetime
from collections import deque
import signal
import sys

# Import weather module
try:
    from weather_display import show_weather_screen
    WEATHER_AVAILABLE = True
except ImportError:
    WEATHER_AVAILABLE = False
    print("⚠️ weather_display.py no encontrado - función de clima deshabilitada")

# Configuration
SERVERS = [
    "8.8.8.8",      # Google DNS
   "1.1.1.1",      # Cloudflare DNS
    "208.67.222.222", # OpenDNS
]
PING_INTERVAL = 3  # seconds between pings
PING_TIMEOUT = 2   # seconds before timeout
OUTAGE_THRESHOLD = 3  # consecutive failures to log
PACKET_LOSS_WINDOW = 20  # rolling window for packet loss calculation
SPEEDTEST_INTERVAL = 3600  # seconds between speedtests (1 hour)
MAX_LOG_SIZE = 1024 * 1024 * 1024  # 1GB in bytes
MAX_LOG_AGE_DAYS = 30  # Keep logs for 30 days max
WEATHER_INTERVAL = 60  # seconds between weather screens (1 minute)
WEATHER_DURATION = 30  # seconds to show weather screen
WEATHER_LOCATION = "Prague"  # Change to your location

# Terminal colors and emojis
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Global state
stats = {}
outage_state = {}
speedtest_data = {
    'last_run': None,
    'download': None,
    'upload': None,
    'latency': None,
    'packet_loss': None,
}
display_state = {
    'showing_weather': False,
    'last_weather_show': None,
}
log_file = "connection_outages.log"
speedtest_log_file = "speedtest_history.log"
running = True

def init_stats(server):
    """Initialize statistics for a server"""
    stats[server] = {
        'success': 0,
        'failure': 0,
        'consecutive_failures': 0,
        'last_latency': None,
        'uptime_streak': 0,
        'recent_results': deque(maxlen=PACKET_LOSS_WINDOW),
    }
    outage_state[server] = {
        'in_outage': False,
        'outage_start': None,
        'outage_count': 0,
    }

async def ping_server(server):
    """Ping a server and return latency or None if failed"""
    try:
        process = await asyncio.create_subprocess_exec(
            'ping', '-c', '1', '-W', str(PING_TIMEOUT), server,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        
        if process.returncode == 0:
            # Parse latency from ping output
            match = re.search(r'time[=<](\d+\.?\d*)', stdout.decode())
            if match:
                return float(match.group(1))
        return None
    except Exception:
        return None

def get_latency_emoji(latency):
    """Return emoji based on latency"""
    if latency is None:
        return "❌"
    elif latency < 60:
        return "✅"
    elif latency < 150:
        return "⚠️"
    else:
        return "🔴"

def calculate_packet_loss(server):
    """Calculate packet loss percentage from recent results"""
    recent = stats[server]['recent_results']
    if not recent:
        return 0.0
    failures = sum(1 for r in recent if r is None)
    return (failures / len(recent)) * 100

def log_outage(server, start_time, end_time, count):
    """Log an outage to file"""
    duration = (end_time - start_time).total_seconds()
    check_and_rotate_log(log_file)
    with open(log_file, 'a') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"OUTAGE: {server} | "
                f"Start: {start_time.strftime('%H:%M:%S')} | "
                f"End: {end_time.strftime('%H:%M:%S')} | "
                f"Duration: {duration:.1f}s | "
                f"Missed pings: {count}\n")

def check_and_rotate_log(log_path):
    """Check log size and rotate if needed"""
    import os
    try:
        if os.path.exists(log_path):
            size = os.path.getsize(log_path)
            if size > MAX_LOG_SIZE:
                # Keep only last 30% of file
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                keep_lines = int(len(lines) * 0.3)
                with open(log_path, 'w') as f:
                    f.write(f"[LOG ROTATED - Size exceeded 1GB]\n")
                    f.writelines(lines[-keep_lines:])
    except Exception:
        pass

async def run_speedtest():
    """Run speedtest and parse results"""
    try:
        process = await asyncio.create_subprocess_exec(
            'speedtest', '--format=json', '--accept-license', '--accept-gdpr',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            import json
            data = json.loads(stdout.decode())
            
            # Extract relevant data
            download_mbps = data.get('download', {}).get('bandwidth', 0) * 8 / 1_000_000
            upload_mbps = data.get('upload', {}).get('bandwidth', 0) * 8 / 1_000_000
            latency = data.get('ping', {}).get('latency', 0)
            packet_loss = data.get('packetLoss', 0)
            
            # Update global state
            speedtest_data['last_run'] = datetime.now()
            speedtest_data['download'] = download_mbps
            speedtest_data['upload'] = upload_mbps
            speedtest_data['latency'] = latency
            speedtest_data['packet_loss'] = packet_loss
            
            # Log to file
            check_and_rotate_log(speedtest_log_file)
            with open(speedtest_log_file, 'a') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                        f"Download: {download_mbps:.2f} Mbps | "
                        f"Upload: {upload_mbps:.2f} Mbps | "
                        f"Latency: {latency:.2f} ms | "
                        f"Packet Loss: {packet_loss:.1f}%\n")
            
            return True
    except Exception as e:
        # If speedtest fails, just skip it
        return False

async def speedtest_scheduler():
    """Run speedtest periodically"""
    # Run immediately on start
    await run_speedtest()
    
    while running:
        await asyncio.sleep(SPEEDTEST_INTERVAL)
        if running:
            await run_speedtest()

async def monitor_servers_sequential():
    """Monitor all servers sequentially with delay between each"""
    while running:
        for server in SERVERS:
            if not running:
                break
                
            latency = await ping_server(server)
            
            # Update stats
            if latency is not None:
                stats[server]['success'] += 1
                stats[server]['consecutive_failures'] = 0
                stats[server]['last_latency'] = latency
                stats[server]['uptime_streak'] += 1
                
                # Check if outage ended
                if outage_state[server]['in_outage']:
                    outage_state[server]['in_outage'] = False
                    log_outage(
                        server,
                        outage_state[server]['outage_start'],
                        datetime.now(),
                        outage_state[server]['outage_count']
                    )
            else:
                stats[server]['failure'] += 1
                stats[server]['consecutive_failures'] += 1
                stats[server]['uptime_streak'] = 0
                
                # Check if outage started
                if stats[server]['consecutive_failures'] == OUTAGE_THRESHOLD:
                    outage_state[server]['in_outage'] = True
                    outage_state[server]['outage_start'] = datetime.now()
                    outage_state[server]['outage_count'] = OUTAGE_THRESHOLD
                elif outage_state[server]['in_outage']:
                    outage_state[server]['outage_count'] += 1
            
            # Store result for packet loss calculation
            stats[server]['recent_results'].append(latency)
            
            # Wait before next server
            await asyncio.sleep(PING_INTERVAL)

def draw_dashboard():
    """Draw the live dashboard"""
    # Clear screen
    print("\033[2J\033[H", end="")
    
    # Header
    print(f"{BOLD}{CYAN}╔═══════════════════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║                         CONNECTION DOWN DETECTOR                                  ║{RESET}")
    print(f"{BOLD}{CYAN}╚═══════════════════════════════════════════════════════════════════════════════════╝{RESET}\n")
    
    # Timestamp
    print(f"{BOLD}Last Update:{RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Speedtest results
    if speedtest_data['last_run']:
        print(f"{BOLD}{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━ SPEEDTEST RESULTS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
        last_run_str = speedtest_data['last_run'].strftime('%H:%M:%S')
        time_ago = (datetime.now() - speedtest_data['last_run']).total_seconds() / 60
        next_test = SPEEDTEST_INTERVAL / 60 - time_ago
        
        print(f"{BOLD}Last Test:{RESET} {last_run_str} ({int(time_ago)} min ago) | "
              f"{BOLD}Next Test:{RESET} in {int(next_test)} min")
        print(f"{GREEN}⬇ Download:{RESET} {speedtest_data['download']:.2f} Mbps | "
              f"{YELLOW}⬆ Upload:{RESET} {speedtest_data['upload']:.2f} Mbps | "
              f"{CYAN}⏱ Latency:{RESET} {speedtest_data['latency']:.2f} ms | "
              f"{RED}📉 Loss:{RESET} {speedtest_data['packet_loss']:.1f}%")
        print(f"{CYAN}{'━' * 87}{RESET}\n")
    
    # Table header
    print(f"{BOLD}{'Server':<20} {'Status':<8} {'Latency':<12} {'Success':<10} {'Fail':<8} {'Consecutive':<13} {'Loss %':<10} {'Uptime':<10}{RESET}")
    print("─" * 100)
    
    # Table rows
    for server in SERVERS:
        if server not in stats:
            continue
        
        s = stats[server]
        latency = s['last_latency']
        emoji = get_latency_emoji(latency)
        latency_str = f"{latency:.1f}ms" if latency else "TIMEOUT"
        loss = calculate_packet_loss(server)
        
        # Color coding
        if s['consecutive_failures'] >= OUTAGE_THRESHOLD:
            color = RED
        elif s['consecutive_failures'] > 0:
            color = YELLOW
        else:
            color = GREEN
        
        print(f"{color}{server:<20} {emoji:<8} {latency_str:<12} "
              f"{s['success']:<10} {s['failure']:<8} "
              f"{s['consecutive_failures']:<13} {loss:>6.1f}% "
              f"{s['uptime_streak']:>8}{RESET}")
    
    print("\n" + "─" * 100)
    print(f"{BOLD}Legend:{RESET} ✅ <60ms | ⚠️ 60-150ms | 🔴 >150ms | ❌ Timeout")
    print(f"{BOLD}Logs:{RESET} {log_file} | {speedtest_log_file}")
    print(f"\n{YELLOW}Press Ctrl+C to stop and see summary{RESET}")

async def update_display():
    """Update display periodically"""
    while running:
        if not display_state['showing_weather']:
            draw_dashboard()
        await asyncio.sleep(1)

async def weather_scheduler():
    """Show weather screen periodically"""
    if not WEATHER_AVAILABLE:
        return
    
    # Wait a bit before first weather display
    await asyncio.sleep(WEATHER_INTERVAL)
    
    while running:
        if running:
            # Mark that we're showing weather
            display_state['showing_weather'] = True
            display_state['last_weather_show'] = datetime.now()
            
            # Show weather screen
            await show_weather_screen(WEATHER_DURATION, WEATHER_LOCATION)
            
            # Back to normal display
            display_state['showing_weather'] = False
            
            # Wait until next weather display
            await asyncio.sleep(WEATHER_INTERVAL - WEATHER_DURATION)

def print_summary():
    """Print final summary on exit"""
    print("\n\n" + "=" * 100)
    print(f"{BOLD}{CYAN}FINAL SUMMARY{RESET}")
    print("=" * 100 + "\n")
    
    for server in SERVERS:
        if server not in stats:
            continue
        s = stats[server]
        total = s['success'] + s['failure']
        success_rate = (s['success'] / total * 100) if total > 0 else 0
        
        print(f"{BOLD}{server}:{RESET}")
        print(f"  Total pings: {total}")
        print(f"  Success: {s['success']} ({success_rate:.1f}%)")
        print(f"  Failures: {s['failure']} ({100-success_rate:.1f}%)")
        print(f"  Overall packet loss: {calculate_packet_loss(server):.1f}%")
        print()
    
    print(f"Outages logged to: {log_file}\n")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global running
    if not running:
        # If already shutting down, force exit
        print(f"\n{RED}Force exit...{RESET}")
        sys.exit(0)
    
    running = False
    print(f"\n{YELLOW}Shutting down gracefully...{RESET}")

async def main():
    """Main entry point"""
    global running
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize stats for all servers
    for server in SERVERS:
        init_stats(server)
    
    # Create log files with headers
    with open(log_file, 'a') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"Monitoring started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*80}\n")
    
    with open(speedtest_log_file, 'a') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"Speedtest logging started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*80}\n")
    
    # Start monitoring task (sequential)
    tasks = []
    tasks.append(asyncio.create_task(monitor_servers_sequential()))
    
    # Start speedtest scheduler
    tasks.append(asyncio.create_task(speedtest_scheduler()))
    
    # Start display update task
    tasks.append(asyncio.create_task(update_display()))
    
    # Start weather scheduler
    if WEATHER_AVAILABLE:
        tasks.append(asyncio.create_task(weather_scheduler()))
    
    # Wait for shutdown signal
    try:
        while running:
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        running = False
    
    # Cancel all tasks
    for task in tasks:
        task.cancel()
    
    # Wait for tasks to complete cancellation
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        pass
    
    # Print summary
    print_summary()

if __name__ == "__main__":
    asyncio.run(main())
