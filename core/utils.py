import os
import re
from urllib.parse import urlparse, unquote

def format_bytes(bytes_count: float) -> str:
    """Format bytes into human-readable string (B, KB, MB, GB)."""
    if bytes_count < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0 or unit == 'TB':
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} TB"

def format_speed(bytes_per_sec: float) -> str:
    """Format download speed into human-readable string."""
    if bytes_per_sec <= 0:
        return "0.0 KB/s"
    return f"{format_bytes(bytes_per_sec)}/s"

def format_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    if seconds is None or seconds < 0 or seconds == float('inf'):
        return "--:--"
    seconds = int(round(seconds))
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    if hrs > 0:
        return f"{hrs:02d}s {mins:02d}d {secs:02d}sn"
    return f"{mins:02d}d {secs:02d}sn"

def extract_filename(url: str, headers: dict = None) -> str:
    """Extract clean filename from Content-Disposition header or URL."""
    if headers:
        cd = headers.get('content-disposition', '') or headers.get('Content-Disposition', '')
        if cd:
            filenames = re.findall(r'filename\*?=(?:UTF-8\'\')?["\']?([^";\n]+)["\']?', cd, re.IGNORECASE)
            if filenames:
                return os.path.basename(unquote(filenames[0].strip()))

    parsed = urlparse(url)
    path = unquote(parsed.path)
    filename = os.path.basename(path).strip()
    if not filename or '.' not in filename:
        return "downloaded_file.bin"
    return filename

