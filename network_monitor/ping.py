# ==============================================================================
# SECTION: IMPORTS
# ==============================================================================

# Import the platform module to identify the operating system environment.
import platform
# Import the regex (re) module to parse latency values from command output.
import re
# Import the subprocess module to run the system's native ping command.
import subprocess
# Import the sys module to check for specific platform strings like 'win32'.
import sys

# Import the timeout settings from the consolidated configuration file.
from network_monitor.config import PING_TIMEOUT_MS, PING_TIMEOUT_SEC

# ==============================================================================
# SECTION: HELPER FUNCTIONS
# ==============================================================================

# Define a private helper function to generate the ping command list for the active OS.
def _ping_command(host: str) -> list[str]:
    # Check if the program is running on a Windows system.
    if sys.platform == "win32":
        # Return Windows ping command: send 1 packet, with timeout specified in milliseconds.
        return ["ping", "-n", "1", "-w", str(PING_TIMEOUT_MS), host]
    
    # Otherwise, assume a Unix-like system (macOS or Linux).
    # Send 1 packet, with timeout specified in seconds (minimum 1 second).
    return ["ping", "-c", "1", "-W", str(max(1, int(PING_TIMEOUT_SEC))), host]

# Define a private helper function to parse the round-trip latency from the ping command output.
def _parse_latency(output: str) -> float | None:
    # Compile regex patterns that match French and English ping formats for both Windows and Unix.
    patterns = [
        # Match French Windows output format: e.g., "temps=12 ms" or "temps<1 ms"
        r"temps[=<]\s*(\d+(?:[.,]\d+)?)\s*ms",
        # Match English Windows/Linux output format: e.g., "time=12.5 ms" or "time<1 ms"
        r"time[=<]\s*(\d+(?:[.,]\d+)?)\s*ms",
        # Match French variant format: e.g., "temps = 12 ms"
        r"temps\s*=\s*(\d+(?:[.,]\d+)?)\s*ms",
        # Fallback format for general ping outputs: e.g., "12 ms ttl=64"
        r"(\d+(?:[.,]\d+)?)\s*ms\s+ttl=",
    ]
    # Search the output against each regex pattern.
    for pattern in patterns:
        # Search the ping command output with case insensitivity.
        match = re.search(pattern, output, re.IGNORECASE)
        # If a match is found, return the parsed latency value.
        if match:
            # Replace comma with dot to handle European locale representations (like "1,5 ms").
            clean_number = match.group(1).replace(",", ".")
            # Convert the clean string representation to a floating point number.
            return float(clean_number)
    # Return None if no pattern matched.
    return None

# ==============================================================================
# SECTION: PUBLIC API
# ==============================================================================

# Define the public function to execute a ping check on a target host.
def ping_host(host: str) -> tuple[bool, float | None]:
    try:
        # Check if the host operating system is Windows to determine process creation flags.
        if platform.system() == "Windows":
            # On Windows, suppress the popup console window by setting CREATE_NO_WINDOW flag.
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            # No special flags needed on non-Windows systems.
            flags = 0
        
        # Run the system's native ping command using subprocess.
        result = subprocess.run(
            # Generate the command line arguments list.
            _ping_command(host),
            # Capture standard output and error output so we can parse them.
            capture_output=True,
            # Decode the raw stdout and stderr bytes into standard strings.
            text=True,
            # Set a safety timeout to prevent the process from hanging indefinitely.
            timeout=PING_TIMEOUT_SEC + 1.0,
            # Pass the window creation flags to keep execution invisible.
            creationflags=flags
        )
    # Catch timeout errors or file system/OS command-not-found exceptions.
    except (subprocess.TimeoutExpired, OSError):
        # Return False for status and None for latency if the command timed out or failed.
        return False, None

    # Combine stdout and stderr into a single string for parsing.
    output = result.stdout + result.stderr
    # Consider the host reachable if the exit code is 0.
    is_up = result.returncode == 0

    # If the return code is not 0, the machine did not respond to the ping request.
    if not is_up:
        # Return False indicating the host is offline.
        return False, None

    # Parse latency from the output and return it along with the UP status.
    return True, _parse_latency(output)
