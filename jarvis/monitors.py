"""Live system stats for the panel monitors. psutil is optional:
read_stats() returns None when it is missing so the UI degrades cleanly.
"""
import shutil


def read_stats():
    """Return {'cpu': %, 'ram': %, 'disk': %} or None if psutil is missing."""
    try:
        import psutil
    except ImportError:
        return None
    try:
        disk = shutil.disk_usage("C:\\" if __import__("os").name == "nt" else "/")
        return {
            "cpu": round(psutil.cpu_percent(interval=None)),
            "ram": round(psutil.virtual_memory().percent),
            "disk": round(disk.used / disk.total * 100),
        }
    except Exception:
        return None


def format_stats(stats):
    """One-line label text for the panel. Testable without psutil."""
    if not stats:
        return "CPU --%  •  RAM --%  •  Disk --%"
    return (
        f"CPU {stats['cpu']}%  •  RAM {stats['ram']}%  •  Disk {stats['disk']}%"
    )
