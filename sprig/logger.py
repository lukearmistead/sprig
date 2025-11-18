"""Simple logging for Sprig CLI."""
import logging
import os
import sys


def get_logger(name: str = "sprig") -> logging.Logger:
    """Get a console logger with configurable level."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

    logger.setLevel(level)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(handler)
    return logger
