# ==============================================================================
# SECTION: IMPORTS
# ==============================================================================

# Import dataclasses to define clean structured data containers without boilerplate.
from dataclasses import dataclass, field
# Import datetime and timedelta to keep track of ping check times and downtime durations.
from datetime import datetime, timedelta
# Import Enum to represent fixed states for machine connectivity (UP / DOWN).
from enum import Enum

# ==============================================================================
# SECTION: DATA TYPE DEFINITIONS & ENUMS
# ==============================================================================

# Define a Status enum representing the online state of a machine.
class Status(Enum):
    # The machine is online and responding.
    UP = "UP"
    # The machine is offline or failed to respond.
    DOWN = "DOWN"

# Define a dataclass to hold the state of a monitored machine.
@dataclass
class Machine:
    # The display name of the machine.
    name: str
    # The IP address or hostname of the machine.
    ip: str
    # The current status of the machine, defaulting to DOWN.
    status: Status = Status.DOWN
    # The timestamp when the machine was last seen online, initially None.
    last_seen: datetime | None = None
    # The timestamp of the last ping check attempt, initially None.
    last_check: datetime | None = None
    # The timestamp since when the machine has been offline, initially None.
    down_since: datetime | None = None
    # The GUI category section the machine belongs to, defaulting to "Default".
    section: str = "Default"

# Define a dataclass to represent a completed downtime incident.
@dataclass
class DowntimeRecord:
    # The name of the machine that went offline.
    machine_name: str
    # The IP address of the machine that went offline.
    machine_ip: str
    # The timestamp when the machine transitioned to DOWN.
    went_down: datetime
    # The timestamp when the machine transitioned back to UP.
    came_back_up: datetime

    # Calculate the elapsed duration of this downtime incident.
    @property
    def duration(self) -> timedelta:
        # Subtract the downtime start time from the recovery time.
        return self.came_back_up - self.went_down

# Define a dataclass for transferring the monitor state to the GUI.
@dataclass
class MonitorSnapshot:
    # The list of machine objects, defaulting to an empty list.
    machines: list[Machine] = field(default_factory=list)
    # The count of machines currently UP, defaulting to 0.
    up_count: int = 0
    # The count of machines currently DOWN, defaulting to 0.
    down_count: int = 0
    # The timestamp of the last completed check cycle, initially None.
    last_cycle: datetime | None = None
    # The list of historical downtime incidents, defaulting to an empty list.
    archive: list[DowntimeRecord] = field(default_factory=list)

# ==============================================================================
# SECTION: INVENTORY LOADING UTILITIES
# ==============================================================================

# Define a function to parse the machines list from a plain text file.
def load_machines(filepath: str) -> list[Machine]:
    # Initialize an empty list to collect parsed machine instances.
    machines = []
    # Keep track of IP addresses we have already loaded to avoid monitoring duplicates.
    seen_ips = set()

    # Open the file at the specified path in read mode with UTF-8 encoding.
    with open(filepath, encoding="utf-8") as fh:
        # Iterate through each line of the file, tracking the line number for error reporting.
        for line_no, raw in enumerate(fh, start=1):
            # Remove any leading and trailing whitespace from the raw line.
            line = raw.strip()
            # Skip empty lines and lines starting with '#' which are treated as comments.
            if not line or line.startswith("#"):
                # Continue to the next line.
                continue

            # Split the line by whitespace characters into individual fields.
            parts = line.split()
            # Ensure the line contains at least the machine name and the IP address.
            if len(parts) < 2:
                # Raise a helpful formatting error if there are too few fields.
                raise ValueError(
                    f"{filepath}:{line_no} — invalid format (expected: Name IP [Section])"
                )

            # Extract the machine name from the first part.
            name = parts[0]
            # Extract the IP address from the second part.
            ip = parts[1]
            # Extract the section name if present, otherwise default to "Default".
            section = parts[2] if len(parts) > 2 else "Default"

            # Check if this IP address has already been processed to enforce uniqueness.
            if ip in seen_ips:
                # Skip duplicate IP addresses.
                continue
            # Add the IP address to the set of seen IPs.
            seen_ips.add(ip)
            # Create a new Machine instance and append it to our list.
            machines.append(Machine(name=name, ip=ip, section=section))

    # Raise an error if the machines file did not contain any valid machines to monitor.
    if not machines:
        # Inform the user that no records were parsed.
        raise ValueError(f"No machines found in {filepath}")

    # Return the final list of valid, unique machines.
    return machines
