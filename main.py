#!/usr/bin/env python3
"""
Network Monitor — ICMP supervision with real-time GUI.

Usage:
    python main.py                  # default machines.txt
    python main.py path/to/file.txt # custom inventory
"""

import argparse
import sys

from network_monitor.gui import MonitorGUI
from network_monitor.monitor import NetworkMonitor
from network_monitor.config import MACHINES_FILE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Supervision réseau ICMP — dashboard temps réel",
    )
    parser.add_argument(
        "machines_file",
        nargs="?",
        default=MACHINES_FILE,
        help="Fichier d'inventaire (format: NomMachine IP)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Nombre de threads parallèles pour les pings (défaut: 10)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        monitor = NetworkMonitor(
            machines_file=args.machines_file,
            max_workers=args.workers,
        )
        monitor.start()
    except FileNotFoundError:
        print(f"Erreur : fichier introuvable — {args.machines_file}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    gui = MonitorGUI(monitor)
    gui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
