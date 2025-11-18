"""Simple logging for Sprig CLI."""
import logging
import os
import sys


def get_logger(name: str = "sprig") -> logging.Logger:
    """Get a console logger with configurable level.

    Only the root 'sprig' logger gets a handler. Child loggers
    (e.g., 'sprig.auth', 'sprig.sync') propagate to the root.
    """
    logger = logging.getLogger(name)

    # Only add a handler to the root 'sprig' logger
    # Child loggers will propagate to it, avoiding duplicate messages
    if name == "sprig" and not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

        logger.setLevel(level)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger.addHandler(handler)

    return logger
