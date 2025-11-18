"""Tests for the logging configuration."""

import logging
from sprig.logger import get_logger


def test_root_logger_has_handler():
    """Root 'sprig' logger should have exactly one handler."""
    logger = get_logger()
    assert len(logger.handlers) == 1


def test_child_logger_has_no_handler():
    """Child loggers should have no handlers and rely on propagation."""
    # First ensure root logger exists
    get_logger()

    # Create child loggers
    auth_logger = get_logger("sprig.auth")
    sync_logger = get_logger("sprig.sync")

    assert len(auth_logger.handlers) == 0
    assert len(sync_logger.handlers) == 0


def test_no_double_logging(caplog):
    """Messages from child loggers should only appear once.

    This test verifies that child loggers don't create duplicate messages
    due to having their own handlers plus propagation to parent handlers.
    """
    # Clear any existing logs
    caplog.clear()

    # Set up logging capture
    with caplog.at_level(logging.INFO):
        # Get root logger (creates handler)
        root_logger = get_logger()

        # Get child logger (no handler)
        child_logger = get_logger("sprig.auth")

        # Verify handler configuration
        assert len(root_logger.handlers) == 1, "Root logger should have 1 handler"
        assert len(child_logger.handlers) == 0, "Child logger should have 0 handlers"

        # Log a message
        test_message = "Test message for double logging"
        child_logger.info(test_message)

        # Check that message was logged exactly once
        matching_records = [r for r in caplog.records if test_message in r.message]
        assert len(matching_records) == 1, f"Expected 1 log record, found {len(matching_records)}"


def test_child_logger_propagates_to_root():
    """Child loggers should propagate to root."""
    get_logger()  # Create root
    child_logger = get_logger("sprig.auth")

    assert child_logger.propagate is True
    assert child_logger.parent.name == "sprig"
