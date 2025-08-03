"""
System Stats Command for Sir Tim the Timely

Shows server stats like CPU, memory, temperature, etc. (neofetch-style, no username)
"""

import hikari
import arc
import psutil
import platform
from datetime import datetime, timezone

try:
    import cpuinfo
except ImportError:
    cpuinfo = None
try:
    import sensors
except ImportError:
    sensors = None

plugin = arc.GatewayPlugin("sysstats")

@plugin.include
@arc.slash_command("sysstats", "Show server stats (CPU, memory, temp, etc.)")
async def sysstats(ctx: arc.GatewayContext) -> None:
    """Show system stats in a neofetch-style embed."""
    await ctx.defer()
    uname = platform.uname()
    cpu = cpuinfo.get_cpu_info()["brand_raw"] if cpuinfo else uname.processor
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)

    # Visual bars
    def bar(percent, length=16, color_emoji="🟩", empty_emoji="⬜"):
        filled = int(percent / 100 * length)
        return color_emoji * filled + empty_emoji * (length - filled)

    # Temperature (psutil.sensors_temperatures only works on Linux/FreeBSD)
    temp = None
    temp_str = ""
    if hasattr(psutil, "sensors_temperatures"):
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current:
                            temp = entry.current
                            temp_str = f"{temp:.1f}°C ({name})"
                            break
                    if temp:
                        break
        except Exception:
            temp_str = "Unavailable"
    if temp is None and not temp_str:
        if platform.system() == "Darwin":
            temp_str = "Not supported on macOS"
        else:
            temp_str = "Unknown"
    elif temp is not None:
        if temp >= 80:
            temp_str += " 🔥"
        elif temp >= 60:
            temp_str += " ⚠️"
        else:
            temp_str += " 🟢"

    # Memory bar
    mem_bar = bar(mem.percent, color_emoji="🟦", empty_emoji="⬜")
    # CPU bar
    cpu_bar = bar(cpu_percent, color_emoji="🟥", empty_emoji="⬜")

    # Uptime
    uptime = datetime.now(timezone.utc) - boot_time
    days, remainder = divmod(uptime.total_seconds(), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m"

    # Memory calculation: percent is (total - available) / total * 100
    used_mb = (mem.total - mem.available) // (1024 ** 2)
    total_mb = mem.total // (1024 ** 2)
    embed = hikari.Embed(
        title="🖥️ Server Stats",
        description=f"**OS:** `{uname.system} {uname.release} ({uname.machine})`\n"
                    f"**CPU:** `{cpu}`\n"
                    f"**CPU Usage:** {cpu_percent}%\n{cpu_bar}"
                    f"\n**Memory:** {used_mb}MB / {total_mb}MB ({mem.percent}%)\n{mem_bar}"
                    f"\n**Uptime:** `{uptime_str}`\n"
                    f"**Temperature:** `{temp_str}`",
        color=0x3498DB,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="Sir Tim the Timely • System Stats")
    await ctx.respond(embed=embed)

@arc.loader
def load(client: arc.GatewayClient) -> None:
    client.add_plugin(plugin)

@arc.unloader
def unload(client: arc.GatewayClient) -> None:
    client.remove_plugin(plugin)
