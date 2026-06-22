"""Cross-platform ICMP ping via subprocess."""

import platform
import re
import subprocess
import sys

from network_monitor.config import PING_TIMEOUT_MS, PING_TIMEOUT_SEC


def _ping_command(host: str) -> list[str]:
    """Build the platform-specific ping command."""
    if sys.platform == "win32":
        # -n 1 : one packet | -w : timeout in milliseconds
        return ["ping", "-n", "1", "-w", str(PING_TIMEOUT_MS), host]
    # Linux / macOS — -c 1 : one packet | -W : timeout in seconds
    return ["ping", "-c", "1", "-W", str(max(1, int(PING_TIMEOUT_SEC))), host]


def _parse_latency(output: str) -> float | None:
    """Extract round-trip time in milliseconds from ping output."""
    patterns = [
        r"temps[=<]\s*(\d+(?:[.,]\d+)?)\s*ms",          # French Windows
        r"time[=<]\s*(\d+(?:[.,]\d+)?)\s*ms",           # English Windows / Linux
        r"temps\s*=\s*(\d+(?:[.,]\d+)?)\s*ms",          # French variant
        r"(\d+(?:[.,]\d+)?)\s*ms\s+ttl=",               # fallback
    ]
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def ping_host(host: str) -> tuple[bool, float | None]:
    """
    Ping a host once.

    Returns:
        (is_up, latency_ms) — latency_ms is None when host is down or unparseable.
    """
    try:
        result = subprocess.run(
            _ping_command(host),
            capture_output=True,
            text=True,
            timeout=PING_TIMEOUT_SEC + 1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if platform.system() == "Windows"
            else 0,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False, None

    output = result.stdout + result.stderr
    is_up = result.returncode == 0

    if not is_up:
        return False, None

    return True, _parse_latency(output)
