"""
Centralized logging configuration for Sprig CLI.

Provides consistent, user-friendly logging across all commands with
configurable log levels and optional file output.
"""

import logging
import os
import sys
from typing import Optional


def setup_logger(name: str = "sprig") -> logging.Logger:
    """
    Configure and return a logger for Sprig CLI.

    Reads configuration from environment variables:
    - LOG_LEVEL: DEBUG, INFO, WARNING, ERROR (default: INFO)
    - LOG_FILE: Optional file path for logging output

    Args:
        name: Logger name (default: "sprig")

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # Get log level from environment
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    # Create formatter with user-friendly format
    # For INFO and above: clean messages without logger name
    # For DEBUG: include logger name and timestamp
    if log_level <= logging.DEBUG:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        formatter = logging.Formatter("%(message)s")

    # Console handler (stdout for INFO/DEBUG, stderr for WARNING/ERROR)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Use custom filter to route WARNING+ to stderr
    class StdoutFilter(logging.Filter):
        def filter(self, record):
            return record.levelno < logging.WARNING

    class StderrFilter(logging.Filter):
        def filter(self, record):
            return record.levelno >= logging.WARNING

    # Split output between stdout and stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(StdoutFilter())

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)
    stderr_handler.addFilter(StderrFilter())

    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)

    # Optional file handler
    log_file = os.getenv("LOG_FILE")
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setLevel(log_level)
            # File logs always include full context
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            logger.debug(f"Logging to file: {log_file}")
        except Exception as e:
            logger.warning(f"Failed to setup file logging: {e}")

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get or create a logger instance.

    Args:
        name: Optional logger name (default: "sprig")

    Returns:
        Logger instance
    """
    logger_name = name or "sprig"
    return setup_logger(logger_name)
