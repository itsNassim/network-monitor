"""Configuration constants for the network monitor."""

import os

# Paths (relative to project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MACHINES_FILE = os.path.join(PROJECT_ROOT, "machines.txt")
LOG_FILE = os.path.join(PROJECT_ROOT, "monitor.log")

# Ping settings
PING_TIMEOUT_SEC = 1.5          # max wait per ping attempt
PING_TIMEOUT_MS = int(PING_TIMEOUT_SEC * 1000)

# Monitoring intervals (seconds)
INTERVAL_UP = 60                # machines that are UP
INTERVAL_DOWN = 3               # machines that are DOWN (2–5 s range)

# GUI refresh rate (milliseconds)
GUI_REFRESH_MS = 500

# Visual alert: flash DOWN rows every N GUI ticks
DOWN_FLASH_INTERVAL = 2
