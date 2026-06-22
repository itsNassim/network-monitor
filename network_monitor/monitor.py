# ==============================================================================
# SECTION: IMPORTS
# ==============================================================================

# Import the csv library to export downtime history logs to CSV files.
import csv
# Import the json library to parse and serialize cache history.
import json
# Import the os library to verify files exist and create folders.
import os
# Import threading to manage locks and stop events across threads safely.
import threading
# Import ThreadPoolExecutor to ping multiple IP addresses concurrently.
from concurrent.futures import ThreadPoolExecutor, as_completed
# Import datetime and timedelta to record timestamps and durations.
from datetime import datetime, timedelta

# Import logging configuration and settings managers from the unified config.
from network_monitor.config import setup_logging, get_settings, save_settings
# Import structures representing machines, snapshots, states, and downtime incidents.
from network_monitor.models import Machine, MonitorSnapshot, Status, DowntimeRecord, load_machines
# Import the platform-independent ping execution function.
from network_monitor.ping import ping_host

# ==============================================================================
# SECTION: NETWORK MONITOR ENGINE CLASS
# ==============================================================================

# Define the NetworkMonitor class representing the background polling worker engine.
class NetworkMonitor:

    # Initialize the network monitor with the inventory filepath and thread count limits.
    def __init__(self, machines_file: str, max_workers: int = 10) -> None:
        # Store the path to the inventory file containing machine names and IPs.
        self.machines_file = machines_file
        # Store the maximum count of parallel threads allowed in the ping pool.
        self.max_workers = max_workers
        # Set up logging and capture the logger instance for recording events.
        self._logger = setup_logging()
        # Create an empty list to store active machine records.
        self._machines = []
        # Create an empty list to store historical downtime incidents.
        self._archive = []
        # Track the timestamp of the last automated CSV export, initially None.
        self._last_export_date = None
        # Create a threading Lock to ensure safe, serialized access to shared memory.
        self._lock = threading.Lock()
        # Create a threading Event to coordinate a graceful shutdown of the loop.
        self._stop_event = threading.Event()
        # Create a list to keep track of active background thread objects.
        self._threads = []
        # Load user configuration preferences from settings.json.
        self._settings = get_settings()
        # Reconstruct the historical log records from the local cache file.
        self._load_cache()

    # Define a helper function to calculate the local cache file path and ensure its folder exists.
    def _get_cache_path(self) -> str:
        # Define the cache directory name.
        cache_dir = "cache"
        # Create the cache directory if it does not already exist.
        os.makedirs(cache_dir, exist_ok=True)
        # Combine the directory name with the cache filename and return the path.
        return os.path.join(cache_dir, "archive.json")

    # Define a helper function to load and parse cached downtime records from disk.
    def _load_cache(self) -> None:
        # Get the absolute or relative cache filepath.
        path = self._get_cache_path()
        # Check if the cache file exists on the disk.
        if os.path.exists(path):
            try:
                # Open the cache file for reading with UTF-8 encoding.
                with open(path, "r", encoding="utf-8") as f:
                    # Parse the JSON array of records.
                    data = json.load(f)
                # Protect list operations with the lock.
                with self._lock:
                    # Loop through each item in the parsed data list.
                    for item in data:
                        # Append a reconstructed DowntimeRecord object to the archive list.
                        self._archive.append(DowntimeRecord(
                            machine_name=item["machine_name"],
                            machine_ip=item["machine_ip"],
                            went_down=datetime.fromisoformat(item["went_down"]),
                            came_back_up=datetime.fromisoformat(item["came_back_up"])
                        ))
                # Log a success message containing the count of loaded records.
                self._logger.info("Loaded %d archive records from cache", len(data))
            # Catch parsing errors or filesystem exceptions.
            except Exception as e:
                # Log the error details.
                self._logger.error("Failed to load archive cache: %s", e)

    # Define a helper function to flush the in-memory archive list to the disk cache file.
    def _save_cache(self) -> None:
        # Get the cache filepath.
        path = self._get_cache_path()
        try:
            # Safely read from the archive list using the lock.
            with self._lock:
                # Convert the DowntimeRecord instances into simple dictionary mappings.
                data = [
                    {
                        "machine_name": r.machine_name,
                        "machine_ip": r.machine_ip,
                        "went_down": r.went_down.isoformat(),
                        "came_back_up": r.came_back_up.isoformat(),
                    } for r in self._archive
                ]
            # Open the cache file for writing with UTF-8 encoding.
            with open(path, "w", encoding="utf-8") as f:
                # Serialize the list of dictionaries to formatted JSON.
                json.dump(data, f, indent=4)
        # Catch any serialization or filesystem exceptions.
        except Exception as e:
            # Log the exception details.
            self._logger.error("Failed to save archive cache: %s", e)

    # ==============================================================================
    # SECTION: PUBLIC ENGINE API
    # ==============================================================================

    # Define a method to start the background monitoring loop.
    def start(self) -> None:
        # Load the machine inventory from the specified text file.
        self._machines = load_machines(self.machines_file)
        # Log that the monitoring process has begun.
        self._logger.info(
            "Monitor started — %d machine(s) loaded from %s",
            len(self._machines),
            self.machines_file,
        )

        # Run an initial ping cycle synchronously to determine initial states immediately.
        self._run_cycle(self._machines, log_changes=False)

        # Count the number of online machines at startup.
        up = [m for m in self._machines if m.status == Status.UP]
        # Count the number of offline machines at startup.
        down = [m for m in self._machines if m.status == Status.DOWN]
        # Log the initial scan results summary.
        self._logger.info("Initial scan — UP: %d | DOWN: %d", len(up), len(down))

        # Create a background thread to run the continuous check loop.
        polling_thread = threading.Thread(
            # Define the target function to run in the thread.
            target=self._polling_loop,
            # Assign a friendly name for debugging.
            name="polling",
            # Mark the thread as a daemon so it exits when the main thread stops.
            daemon=True,
        )
        # Start the background thread execution.
        polling_thread.start()
        # Save the thread handle in our list of active threads.
        self._threads = [polling_thread]

    # Define a method to stop the background thread gracefully.
    def stop(self) -> None:
        # Set the stop event to signal the polling loop to terminate.
        self._stop_event.set()

    # Define a method to return a safe, independent copy of the machines list for external editing.
    def get_machines_copy(self) -> list[Machine]:
        # Safely copy the machines list under lock protection.
        with self._lock:
            # Return new Machine objects with duplicated field values.
            return [
                Machine(
                    name=m.name,
                    ip=m.ip,
                    status=m.status,
                    last_seen=m.last_seen,
                    last_check=m.last_check,
                    down_since=m.down_since,
                    section=m.section,
                )
                for m in self._machines
            ]

    # Define a method to update the active machines list and overwrite the inventory file.
    def update_machines(self, machines: list[Machine]) -> None:
        # Replace the active machines list under lock protection.
        with self._lock:
            # Overwrite the in-memory machines list.
            self._machines = machines
        
        # Open the inventory text file for writing with UTF-8 encoding.
        with open(self.machines_file, 'w', encoding='utf-8') as fh:
            # Write standard comments at the top of the file.
            fh.write("# Network Monitor Inventory\n")
            # Write format details.
            fh.write("# Format: MachineeName IP [Section]\n\n")
            # Iterate through the updated list of machines.
            for machine in machines:
                # Include the section name if it is not the default category.
                section_str = f" {machine.section}" if machine.section != "Default" else ""
                # Write the machine record line to the file.
                fh.write(f"{machine.name} {machine.ip}{section_str}\n")
        
        # Log that the inventory file has been successfully updated.
        self._logger.info("Machines list updated and saved to %s", self.machines_file)

    # Define a method to retrieve a consistent state snapshot for the GUI.
    def get_snapshot(self) -> MonitorSnapshot:
        # Retrieve state details under lock protection.
        with self._lock:
            # Reconstruct safe copies of all machines.
            copies = [
                Machine(
                    name=m.name,
                    ip=m.ip,
                    status=m.status,
                    last_seen=m.last_seen,
                    last_check=m.last_check,
                    down_since=m.down_since,
                    section=m.section,
                )
                for m in self._machines
            ]
            # Count the total number of online machines.
            up_count = sum(1 for m in copies if m.status == Status.UP)
            # Create a sorted copy of the downtime archive, newest first.
            sorted_archive = sorted(self._archive, key=lambda r: r.came_back_up, reverse=True)
            # Construct and return the thread-safe snapshot.
            return MonitorSnapshot(
                # Sort the copied machines list by Status value (DOWN first) then name.
                machines=sorted(copies, key=lambda m: (m.status.value, m.name)),
                # Assign the up count.
                up_count=up_count,
                # Assign the down count.
                down_count=len(copies) - up_count,
                # Find the maximum check time among all checked machines.
                last_cycle=max(
                    (m.last_check for m in copies if m.last_check),
                    default=None,
                ),
                # Assign the sorted archive copy.
                archive=sorted_archive,
            )

    # Define a method to return a duplicate of the current settings dictionary.
    def get_settings(self) -> dict:
        # Return a copy to prevent external code from modifying the settings cache directly.
        return self._settings.copy()

    # Define a method to save updated configuration values and apply them.
    def update_settings(self, new_settings: dict) -> None:
        # Save the settings dictionary to the config file on disk.
        save_settings(new_settings)
        # Reload settings into memory.
        self._settings = get_settings()
        # Log the configuration update event.
        self._logger.info("Settings updated: %s", new_settings)

    # ==============================================================================
    # SECTION: INTERNAL ENGINE METHODS
    # ==============================================================================

    # Define the core background polling loop method.
    def _polling_loop(self) -> None:
        # Loop until the stop event is flagged.
        while not self._stop_event.is_set():
            # Check if it is time to auto-export historical records to CSV.
            self._check_and_export_archive()

            # Retrieve a thread-safe copy of the active machines list.
            with self._lock:
                # Copy the list.
                targets = list(self._machines)

            # If targets are loaded, execute a concurrent sweep cycle.
            if targets:
                # Perform the ping sweep.
                self._run_cycle(targets)

            # Retrieve the polling frequency, defaulting to 60 seconds.
            polling_interval = self._settings.get("polling_interval_sec", 60)
            # Wait for the interval, breaking early if the stop event is flagged.
            self._stop_event.wait(polling_interval)

    # Define a method to execute parallel pings for a batch of machines.
    def _run_cycle(self, machines: list[Machine], log_changes: bool = True) -> None:
        # Capture the start timestamp of the check cycle.
        now = datetime.now()

        # Create a thread pool to run pings concurrently.
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            # Map each ping future to its corresponding Machine object.
            future_map = {
                pool.submit(ping_host, m.ip): m for m in machines
            }
            # Retrieve future outcomes as they complete execution.
            for future in as_completed(future_map):
                # Retrieve the corresponding machine record.
                machine = future_map[future]
                try:
                    # Unpack the reachable status and ping latency.
                    is_up, latency = future.result()
                # Catch any unexpected thread execution exceptions.
                except Exception:
                    # Fall back to marking the machine offline.
                    is_up, latency = False, None

                # Determine the machine status outcome.
                new_status = Status.UP if is_up else Status.DOWN
                # Apply result updates to the machine record.
                self._apply_result(machine, new_status, latency, now, log_changes)

    # Define a method to apply ping results and manage status transition logs.
    def _apply_result(
        self,
        machine: Machine,
        new_status: Status,
        latency: float | None,
        checked_at: datetime,
        log_changes: bool = True,
    ) -> None:
        # Modify the machine state under lock protection.
        with self._lock:
            # Keep track of the status before updates.
            old_status = machine.status
            # Update the last checked timestamp.
            machine.last_check = checked_at

            # If the host is online, update its last seen timestamp.
            if new_status == Status.UP:
                # Update last seen.
                machine.last_seen = checked_at

            # If the host is offline and wasn't before, set the offline timestamp.
            if new_status == Status.DOWN and machine.down_since is None:
                # Set down since time.
                machine.down_since = checked_at

            # Check if a status transition occurred.
            if old_status != new_status:
                # Update status attribute.
                machine.status = new_status
                # Handle UP to DOWN transitions.
                if new_status == Status.DOWN:
                    # Log the outage if logging is enabled.
                    if log_changes:
                        # Log message.
                        self._logger.info("Machine %s is DOWN", machine.name)
                # Handle DOWN to UP transitions.
                else:
                    # Verify the machine was previously marked offline.
                    if machine.down_since is not None:
                        # Construct a finalized DowntimeRecord object.
                        record = DowntimeRecord(
                            machine_name=machine.name,
                            machine_ip=machine.ip,
                            went_down=machine.down_since,
                            came_back_up=checked_at,
                        )
                        # Append the downtime incident to the archive.
                        self._archive.append(record)
                        # Save the updated archive list to the cache immediately.
                        self._save_cache()
                        # Log recovery details.
                        if log_changes:
                            # Calculate outage duration.
                            duration = record.duration
                            # Log message.
                            self._logger.info(
                                "Machine %s is UP (was down for %s)",
                                machine.name,
                                duration,
                            )
                    # Reset the offline timer state.
                    machine.down_since = None

    # Define a method to check if automated export conditions are met.
    def _check_and_export_archive(self) -> None:
        # Capture current time.
        now = datetime.now()
        
        # Initialize the last export date timestamp if running for the first time.
        if self._last_export_date is None:
            # Set the reference date.
            self._last_export_date = now
            return
        
        # Retrieve the export interval threshold.
        export_days = self._settings.get("archive_export_days", 30)
        # Calculate the threshold date.
        days_ago = now - timedelta(days=export_days)
        # Perform the export and clear actions if the interval has passed.
        if self._last_export_date < days_ago:
            # Export records.
            self._export_archive_to_csv()
            # Clear records.
            self._clear_archive()
            # Update the reference date.
            self._last_export_date = now

    # Define a method to manually export the downtime logs to a CSV file.
    def export_archive(self) -> str | None:
        # Read the archive records list under lock protection.
        with self._lock:
            # If the archive is empty, return None immediately.
            if not self._archive:
                return None
            # Copy the list.
            archive_copy = list(self._archive)
        
        # Retrieve the logs export folder.
        logs_dir = self._settings.get("logs_directory", "logs")
        # Ensure the output directory exists.
        os.makedirs(logs_dir, exist_ok=True)
        
        # Capture current timestamp.
        now = datetime.now()
        # Retrieve the filename prefix.
        prefix = self._settings.get("archive_export_prefix", "downtime_archive")
        # Generate the unique CSV file name.
        filename = f"{prefix}_manual_{now.strftime('%Y_%m_%d_%H_%M_%S')}.csv"
        # Form the absolute file path.
        filepath = os.path.join(logs_dir, filename)
        
        try:
            # Open the CSV file for writing with UTF-8 encoding.
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                # Define column header names.
                fieldnames = ['Machine Name', 'Machine IP', 'Went DOWN', 'Came Back UP', 'Duration (HH:MM:SS)']
                # Create a DictWriter instance.
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write the header row.
                writer.writeheader()
                
                # Iterate through the copied records list.
                for record in archive_copy:
                    # Calculate the elapsed duration.
                    duration = record.duration
                    # Convert duration to total seconds.
                    total_seconds = int(duration.total_seconds())
                    # Convert total seconds to hours, minutes, and seconds.
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    # Compose the duration string.
                    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    
                    # Write the data row to the CSV file.
                    writer.writerow({
                        'Machine Name': record.machine_name,
                        'Machine IP': record.machine_ip,
                        'Went DOWN': record.went_down.strftime('%Y-%m-%d %H:%M:%S'),
                        'Came Back UP': record.came_back_up.strftime('%Y-%m-%d %H:%M:%S'),
                        'Duration (HH:MM:SS)': duration_str,
                    })
            
            # Log successful manual export.
            self._logger.info("Archive manually exported to %s (%d records)", filepath, len(archive_copy))
            # Return the filepath.
            return filepath
        # Catch any filesystem exceptions.
        except Exception as e:
            # Log the export failure.
            self._logger.error("Failed to manually export archive: %s", e)
            # Re-raise the exception to inform the caller.
            raise e

    # Define a method to manually clear the archive records list.
    def clear_archive(self) -> int:
        # Clear the list under lock protection.
        with self._lock:
            # Count the records to be deleted.
            archive_count = len(self._archive)
            # Clear the list.
            self._archive.clear()
        
        # Flush the empty list state to the disk cache file.
        self._save_cache()
        
        # Log manual clear event.
        self._logger.info("Archive manually cleared (%d records removed)", archive_count)
        # Return the count of removed records.
        return archive_count

    # Define an internal method to automatically export records to CSV.
    def _export_archive_to_csv(self) -> None:
        # Return immediately if there are no records to save.
        if not self._archive:
            # Log event.
            self._logger.info("No archive records to export")
            return
        
        # Retrieve log folder path.
        logs_dir = self._settings.get("logs_directory", "logs")
        # Ensure the folder exists.
        os.makedirs(logs_dir, exist_ok=True)
        
        # Capture current timestamp.
        now = datetime.now()
        # Retrieve the filename prefix.
        prefix = self._settings.get("archive_export_prefix", "downtime_archive")
        # Generate the unique CSV file name.
        filename = f"{prefix}_{now.strftime('%Y_%m_%d_%H_%M_%S')}.csv"
        # Form the absolute file path.
        filepath = os.path.join(logs_dir, filename)
        
        try:
            # Open the CSV file for writing with UTF-8 encoding.
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                # Define column headers.
                fieldnames = ['Machine Name', 'Machine IP', 'Went DOWN', 'Came Back UP', 'Duration (HH:MM:SS)']
                # Create a DictWriter instance.
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header row.
                writer.writeheader()
                
                # Iterate through the records in the archive.
                for record in self._archive:
                    # Calculate duration.
                    duration = record.duration
                    # Convert to seconds.
                    total_seconds = int(duration.total_seconds())
                    # Convert to hours, minutes, and seconds.
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    # Compose the duration string.
                    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    
                    # Write the row.
                    writer.writerow({
                        'Machine Name': record.machine_name,
                        'Machine IP': record.machine_ip,
                        'Went DOWN': record.went_down.strftime('%Y-%m-%d %H:%M:%S'),
                        'Came Back UP': record.came_back_up.strftime('%Y-%m-%d %H:%M:%S'),
                        'Duration (HH:MM:SS)': duration_str,
                    })
            
            # Log successful export.
            self._logger.info("Archive exported to %s (%d records)", filepath, len(self._archive))
        # Catch any filesystem exceptions.
        except Exception as e:
            # Log the export failure.
            self._logger.error("Failed to export archive: %s", e)

    # Define an internal method to clear the archive list.
    def _clear_archive(self) -> None:
        # Clear the list under lock protection.
        with self._lock:
            # Count the records.
            archive_count = len(self._archive)
            # Clear the list.
            self._archive.clear()
        
        # Flush the empty list state to the disk cache file.
        self._save_cache()
        
        # Log clear event.
        self._logger.info("Archive cleared (%d records removed)", archive_count)
