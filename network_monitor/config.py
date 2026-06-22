# ==============================================================================
# SECTION: IMPORTS
# ==============================================================================

# Import os library to handle system-independent file path calculations.
import os
# Import json library to parse and write settings/sections data.
import json
# Import logging library to record status changes and program execution events.
import logging

# ==============================================================================
# SECTION: PATH CONSTANTS
# ==============================================================================

# Find the absolute path to the directory containing this package.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Absolute path to the file containing the list of monitored machines.
MACHINES_FILE = os.path.join(PROJECT_ROOT, "machines.txt")
# Absolute path to the file where logs are saved.
LOG_FILE = os.path.join(PROJECT_ROOT, "monitor.log")
# Absolute path to the sections configuration file.
SECTIONS_FILE = os.path.join(PROJECT_ROOT, "sections.json")
# Absolute path to the settings configuration file.
SETTINGS_FILE = os.path.join(PROJECT_ROOT, "settings.json")

# ==============================================================================
# SECTION: PING CONSTANTS
# ==============================================================================

# Maximum duration (in seconds) to wait for an ICMP reply.
PING_TIMEOUT_SEC = 1.5
# The timeout threshold converted to milliseconds.
PING_TIMEOUT_MS = int(PING_TIMEOUT_SEC * 1000)

# ==============================================================================
# SECTION: MONITORING INTERVAL CONSTANTS
# ==============================================================================

# Frequency (in seconds) to ping a machine that is currently UP.
INTERVAL_UP = 60
# Frequency (in seconds) to ping a machine that is currently DOWN.
INTERVAL_DOWN = 3

# ==============================================================================
# SECTION: GUI CONSTANTS
# ==============================================================================

# Interval in milliseconds at which the main GUI redraws the tables.
GUI_REFRESH_MS = 500
# Count of GUI refresh ticks between toggling the red flash color for DOWN rows.
DOWN_FLASH_INTERVAL = 2

# ==============================================================================
# SECTION: DEFAULT SETTINGS CONFIGURATION
# ==============================================================================

# Default settings dictionary used when settings.json is missing or corrupt.
DEFAULT_SETTINGS = {
    # Frequency of ping checks.
    "polling_interval_sec": 60,
    # Number of days to accumulate history before exporting.
    "archive_export_days": 30,
    # Prefix used for exported CSV log files.
    "archive_export_prefix": "downtime_archive",
    # Path where log and CSV files should be saved.
    "logs_directory": os.path.join(PROJECT_ROOT, "logs"),
}

# ==============================================================================
# SECTION: DEFAULT SECTIONS CONFIGURATION
# ==============================================================================

# Default section list with order and colors.
DEFAULT_SECTIONS = [
    # Fallback default group.
    {"name": "Default", "color": "#4a5a7a", "order": 0},
]

# ==============================================================================
# SECTION: LOGGING SETUP
# ==============================================================================

# Define a function to configure logging output handlers.
def setup_logging() -> logging.Logger:
    # Ensure that the directory containing the log file exists.
    os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)
    # Retrieve the application-wide logger named "network_monitor".
    logger = logging.getLogger("network_monitor")
    # Set the logging level to INFO to capture transitions and errors.
    logger.setLevel(logging.INFO)
    # Clear any existing logging handlers to prevent duplicate messages.
    logger.handlers.clear()
    # Define a consistent format string for log messages.
    formatter = logging.Formatter(
        # Formatted as: YYYY-MM-DD HH:MM:SS | LEVEL | message
        "%(asctime)s | %(levelname)s | %(message)s",
        # Timestamp format details.
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Create a handler to write logs to the file path using UTF-8.
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    # Assign the formatter rules to the file handler.
    file_handler.setFormatter(formatter)
    # Attach the file handler to the logger instance.
    logger.addHandler(file_handler)
    # Create a handler to print logs directly to the command prompt stream.
    console_handler = logging.StreamHandler()
    # Assign the same formatter rules to the console handler.
    console_handler.setFormatter(formatter)
    # Attach the console handler to the logger instance.
    logger.addHandler(console_handler)
    # Return the configured logger.
    return logger

# ==============================================================================
# SECTION: SETTINGS MANAGEMENT FUNCTIONS
# ==============================================================================

# Define a function to load settings from settings.json.
def load_settings() -> dict:
    # Check if the settings file exists on the disk.
    if os.path.exists(SETTINGS_FILE):
        # Open and parse the file.
        try:
            # Open settings.json in read-only mode with UTF-8.
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                # Read json data.
                loaded = json.load(f)
                # Return dictionary combining default options with loaded ones.
                return {**DEFAULT_SETTINGS, **loaded}
        # Catch errors if reading or parsing fails.
        except Exception:
            # Return a copy of the default settings dict.
            return DEFAULT_SETTINGS.copy()
    # Return default settings if settings.json does not exist.
    return DEFAULT_SETTINGS.copy()

# Define a function to save settings to settings.json.
def save_settings(settings: dict) -> None:
    # Create parent folder for settings file if it doesn't exist.
    os.makedirs(os.path.dirname(SETTINGS_FILE) or ".", exist_ok=True)
    # Open settings.json file for writing with UTF-8 encoding.
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        # Dump the settings dict as formatted JSON with a 2-space indentation.
        json.dump(settings, f, indent=2)

# Define a wrapper function to get settings.
def get_settings() -> dict:
    # Call the load_settings function and return the dictionary.
    return load_settings()

# ==============================================================================
# SECTION: SECTIONS MANAGEMENT FUNCTIONS
# ==============================================================================

# Define a function to load list of groups from sections.json.
def load_sections() -> list[dict]:
    # Return a copy of default sections if the file does not exist.
    if not os.path.exists(SECTIONS_FILE):
        # Return default sections.
        return DEFAULT_SECTIONS.copy()
    # Try parsing custom sections from the JSON file.
    try:
        # Open sections.json in read mode with UTF-8 encoding.
        with open(SECTIONS_FILE, "r", encoding="utf-8") as f:
            # Load JSON data.
            data = json.load(f)
            # Retrieve sections list from JSON data, defaulting to copies of DEFAULT_SECTIONS.
            sections = data.get("sections", DEFAULT_SECTIONS.copy())
            # Sort the sections list in-place based on their defined 'order' key.
            sections.sort(key=lambda s: s.get("order", 999))
            # Return sorted sections.
            return sections
    # Catch any file system or decoding errors.
    except Exception:
        # Fall back to default sections list.
        return DEFAULT_SECTIONS.copy()

# Define a function to save custom section lists to sections.json.
def save_sections(sections: list[dict]) -> None:
    # Loop through the list to set the order key based on current list index.
    for i, section in enumerate(sections):
        # Assign numeric index to define the display sorting order.
        section["order"] = i
    # Store the list inside a dictionary wrapper.
    data = {"sections": sections}
    # Open sections.json for writing with UTF-8 encoding.
    with open(SECTIONS_FILE, "w", encoding="utf-8") as f:
        # Write JSON data to the file with a 2-space indentation.
        json.dump(data, f, indent=2, ensure_ascii=False)

# Define a function to look up the color hex string for a given section name.
def get_section_color(section_name: str) -> str:
    # Read sections list.
    sections = load_sections()
    # Loop through every section to find a name match.
    for section in sections:
        # Check if the section name matches the query.
        if section["name"] == section_name:
            # Return the color value of the matched section.
            return section.get("color", "#4a5a7a")
    # Return the default color code if not found.
    return "#4a5a7a"

# Define a function to convert the section lists into a name-to-color dictionary.
def get_sections_dict() -> dict[str, str]:
    # Read sections list.
    sections = load_sections()
    # Construct a dictionary mapping each section name to its color value.
    return {s["name"]: s.get("color", "#4a5a7a") for s in sections}
