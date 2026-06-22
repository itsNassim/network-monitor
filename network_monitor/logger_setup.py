"""Logging setup — state changes only."""

import logging
import os

from network_monitor.config import LOG_FILE


def setup_logging() -> logging.Logger:
    """Configure file + console logging for state transitions."""
    os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)

    logger = logging.getLogger("network_monitor")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
