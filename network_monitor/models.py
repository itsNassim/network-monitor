"""Machine inventory and state models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Status(Enum):
    UP = "UP"
    DOWN = "DOWN"


@dataclass
class Machine:
    name: str
    ip: str
    status: Status = Status.DOWN
    latency_ms: float | None = None
    last_seen: datetime | None = None
    last_check: datetime | None = None


@dataclass
class MonitorSnapshot:
    """Thread-safe read-only view for the GUI."""

    machines: list[Machine] = field(default_factory=list)
    up_count: int = 0
    down_count: int = 0
    last_cycle: datetime | None = None


def load_machines(filepath: str) -> list[Machine]:
    """
    Load machines from a text file.

    Format per line:  NomMachine IP
    Lines starting with # and blank lines are ignored.
    """
    machines: list[Machine] = []
    seen_ips: set[str] = set()

    with open(filepath, encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 2:
                raise ValueError(
                    f"{filepath}:{line_no} — invalid format (expected: Name IP)"
                )

            name, ip = parts[0], parts[1]
            if ip in seen_ips:
                continue
            seen_ips.add(ip)
            machines.append(Machine(name=name, ip=ip))

    if not machines:
        raise ValueError(f"No machines found in {filepath}")

    return machines
