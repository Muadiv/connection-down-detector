#!/usr/bin/env python3
"""
Weather Display Module
Shows weather information using wttr.in service
"""

import subprocess
import asyncio

async def get_weather(location="Prague", lang="es"):
    """
    Fetch weather from wttr.in
    
    Args:
        location: City name or coordinates
        lang: Language code (es, en, cs, etc.)
    
    Returns:
        str: Weather output or error message
    """
    try:
        # wttr.in options:
        # ?0 = current weather only
        # ?1 = current + today
        # ?2 = current + today + tomorrow
        # ?T = no color/formatting (we add our own)
        # ?M = metric units
        # ?lang=es = Spanish
        
        # Use curl to fetch weather
        # Options for compact display on small screen
        url = f"http://wttr.in/{location}?format=v2&lang={lang}"
        
        process = await asyncio.create_subprocess_exec(
            'curl', '-s', '--max-time', '5', url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0 and stdout:
            return stdout.decode('utf-8')
        else:
            return "❌ No se pudo obtener el clima"
            
    except Exception as e:
        return f"❌ Error obteniendo clima: {str(e)}"

async def get_weather_compact(location="Prague"):
    """
    Get compact one-line weather format
    Perfect for small displays
    """
    try:
        # Compact format: just the essentials
        url = f"http://wttr.in/{location}?format=%l:+%C+%t+%h+%w"
        # Format codes:
        # %l = location
        # %C = weather condition
        # %t = temperature
        # %h = humidity
        # %w = wind
        
        process = await asyncio.create_subprocess_exec(
            'curl', '-s', '--max-time', '5', url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0 and stdout:
            return stdout.decode('utf-8').strip()
        else:
            return "❌ No se pudo obtener el clima"
            
    except Exception as e:
        return f"❌ Error: {str(e)}"

def draw_weather_screen(weather_text):
    """
    Draw weather screen with formatting
    """
    # Clear screen
    print("\033[2J\033[H", end="")
    
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    YELLOW = "\033[93m"
    
    # Header
    print(f"{BOLD}{CYAN}╔═══════════════════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║                              INFORMACIÓN DEL CLIMA                                ║{RESET}")
    print(f"{BOLD}{CYAN}╚═══════════════════════════════════════════════════════════════════════════════════╝{RESET}\n")
    
    # Weather content
    print(weather_text)
    
    print(f"\n{YELLOW}Volviendo al monitor en unos segundos...{RESET}")

async def show_weather_screen(duration=30, location="Prague"):
    """
    Show weather screen for specified duration
    
    Args:
        duration: Seconds to show weather
        location: Location for weather
    """
    weather = await get_weather(location)
    draw_weather_screen(weather)
    await asyncio.sleep(duration)

# For testing
if __name__ == "__main__":
    async def test():
        print("Obteniendo clima...")
        weather = await get_weather("Prague")
        draw_weather_screen(weather)
        
        print("\n\n--- Formato compacto ---")
        compact = await get_weather_compact("Prague")
        print(compact)
    
    asyncio.run(test())
