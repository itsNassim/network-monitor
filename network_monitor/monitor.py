"""Monitoring engine — threaded ICMP supervision."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from network_monitor.config import INTERVAL_DOWN, INTERVAL_UP
from network_monitor.logger_setup import setup_logging
from network_monitor.models import Machine, MonitorSnapshot, Status, load_machines
from network_monitor.ping import ping_host


class NetworkMonitor:
    """Continuous ICMP monitor with separate UP/DOWN polling intervals."""

    def __init__(self, machines_file: str, max_workers: int = 10) -> None:
        self.machines_file = machines_file
        self.max_workers = max_workers
        self._logger = setup_logging()
        self._machines: list[Machine] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Load inventory, run initial sweep, then launch worker threads."""
        self._machines = load_machines(self.machines_file)
        self._logger.info(
            "Monitor started — %d machine(s) loaded from %s",
            len(self._machines),
            self.machines_file,
        )

        self._run_cycle(self._machines, log_changes=False)

        up = [m for m in self._machines if m.status == Status.UP]
        down = [m for m in self._machines if m.status == Status.DOWN]
        self._logger.info("Initial scan — UP: %d | DOWN: %d", len(up), len(down))

        self._threads = [
            threading.Thread(
                target=self._poll_loop,
                args=(Status.UP, INTERVAL_UP),
                name="poll-up",
                daemon=True,
            ),
            threading.Thread(
                target=self._poll_loop,
                args=(Status.DOWN, INTERVAL_DOWN),
                name="poll-down",
                daemon=True,
            ),
        ]
        for t in self._threads:
            t.start()

    def stop(self) -> None:
        """Signal all worker threads to stop."""
        self._stop_event.set()

    def get_snapshot(self) -> MonitorSnapshot:
        """Return a consistent copy of current state for the GUI."""
        with self._lock:
            copies = [
                Machine(
                    name=m.name,
                    ip=m.ip,
                    status=m.status,
                    latency_ms=m.latency_ms,
                    last_seen=m.last_seen,
                    last_check=m.last_check,
                )
                for m in self._machines
            ]
            up_count = sum(1 for m in copies if m.status == Status.UP)
            return MonitorSnapshot(
                machines=sorted(copies, key=lambda m: (m.status.value, m.name)),
                up_count=up_count,
                down_count=len(copies) - up_count,
                last_cycle=max(
                    (m.last_check for m in copies if m.last_check),
                    default=None,
                ),
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _poll_loop(self, target_status: Status, interval: float) -> None:
        """Ping machines matching *target_status* every *interval* seconds."""
        while not self._stop_event.is_set():
            with self._lock:
                targets = [m for m in self._machines if m.status == target_status]

            if targets:
                self._run_cycle(targets)

            self._stop_event.wait(interval)

    def _run_cycle(self, machines: list[Machine], log_changes: bool = True) -> None:
        """Ping a batch of machines concurrently and apply state changes."""
        now = datetime.now()

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_map = {
                pool.submit(ping_host, m.ip): m for m in machines
            }
            for future in as_completed(future_map):
                machine = future_map[future]
                try:
                    is_up, latency = future.result()
                except Exception:
                    is_up, latency = False, None

                new_status = Status.UP if is_up else Status.DOWN
                self._apply_result(machine, new_status, latency, now, log_changes)

    def _apply_result(
        self,
        machine: Machine,
        new_status: Status,
        latency: float | None,
        checked_at: datetime,
        log_changes: bool = True,
    ) -> None:
        """Update machine state; log only on transitions."""
        with self._lock:
            old_status = machine.status
            machine.last_check = checked_at

            if new_status == Status.UP:
                machine.latency_ms = latency
                machine.last_seen = checked_at
            else:
                machine.latency_ms = None

            if old_status != new_status:
                machine.status = new_status
                if log_changes:
                    if new_status == Status.UP:
                        self._logger.info("Machine %s is UP", machine.name)
                    else:
                        self._logger.info("Machine %s is DOWN", machine.name)
