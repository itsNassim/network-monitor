#!/usr/bin/env python3
# ==============================================================================
# SECTION: DESCRIPTION & USAGE
# ==============================================================================
"""
Network Monitor — ICMP supervision with real-time GUI.

Usage:
    python main.py                  # default machines.txt
    python main.py path/to/file.txt # custom inventory
"""

# ==============================================================================
# SECTION: IMPORTS
# ==============================================================================

# Import argparse library to parse command line arguments.
import argparse
# Import sys library to write errors to stderr and return status codes.
import sys

# Import the main graphical user interface class.
from network_monitor.gui import MonitorGUI
# Import the background monitor worker engine class.
from network_monitor.monitor import NetworkMonitor
# Import the default machines inventory filepath constant.
from network_monitor.config import MACHINES_FILE

# ==============================================================================
# SECTION: CLI ARGUMENTS PARSING
# ==============================================================================

# Define a function to parse command line arguments.
def parse_args() -> argparse.Namespace:
    # Initialize the argument parser with a description of the program.
    parser = argparse.ArgumentParser(
        description="Supervision réseau ICMP — dashboard temps réel",
    )
    # Add a positional argument for the inventory file path.
    parser.add_argument(
        "machines_file",
        # Make the argument optional.
        nargs="?",
        # Use the default inventory filepath if none is specified.
        default=MACHINES_FILE,
        # Display helper documentation for this argument.
        help="Fichier d'inventaire (format: NomMachine IP)",
    )
    # Add an optional argument to configure parallel worker threads count.
    parser.add_argument(
        "--workers",
        # Restrict the parsed value type to an integer.
        type=int,
        # Default to 10 parallel threads.
        default=10,
        # Display helper documentation for this argument.
        help="Nombre de threads parallèles pour les pings (défaut: 10)",
    )
    # Parse and return the argument Namespace.
    return parser.parse_args()

# ==============================================================================
# SECTION: MAIN ENTRYPOINT
# ==============================================================================

# Define the main application runner function.
def main() -> int:
    # Parse command line arguments.
    args = parse_args()

    try:
        # Create an instance of the NetworkMonitor engine.
        monitor = NetworkMonitor(
            # Pass the inventory filepath argument.
            machines_file=args.machines_file,
            # Pass the maximum concurrent worker threads count.
            max_workers=args.workers,
        )
        # Start background ping checks and launch monitoring threads.
        monitor.start()
    # Catch a missing inventory file exception.
    except FileNotFoundError:
        # Print a clean error message to the standard error stream.
        print(f"Erreur : fichier introuvable — {args.machines_file}", file=sys.stderr)
        # Return status code 1 indicating failure.
        return 1
    # Catch any file format validation exceptions or parsing errors.
    except ValueError as exc:
        # Print the error description to the standard error stream.
        print(f"Erreur : {exc}", file=sys.stderr)
        # Return status code 1 indicating failure.
        return 1

    # Create the graphical interface instance passing the active engine.
    gui = MonitorGUI(monitor)
    # Run the GUI main event loop (blocking).
    gui.run()
    # Return status code 0 indicating successful execution.
    return 0

# ==============================================================================
# SECTION: SYSTEM CALL
# ==============================================================================

# Run the program if executed directly from the shell environment.
if __name__ == "__main__":
    # Call main and exit with its return code.
    sys.exit(main())
