"""Path utilities for Sprig home directory (~/.sprig/)."""

from pathlib import Path

SPRIG_HOME = Path.home() / ".sprig"


def get_sprig_home() -> Path:
    """Get the Sprig home directory (~/.sprig/), creating it if needed."""
    SPRIG_HOME.mkdir(parents=True, exist_ok=True)
    return SPRIG_HOME


def get_default_db_path() -> Path:
    """Get the default database path (~/.sprig/sprig.db)."""
    return get_sprig_home() / "sprig.db"


def get_default_certs_dir() -> Path:
    """Get the default certificates directory (~/.sprig/certs/)."""
    certs_dir = get_sprig_home() / "certs"
    certs_dir.mkdir(parents=True, exist_ok=True)
    return certs_dir


def get_default_exports_dir() -> Path:
    """Get the default exports directory (~/.sprig/exports/)."""
    exports_dir = get_sprig_home() / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    return exports_dir


def get_default_config_path() -> Path:
    """Get the default config file path (~/.sprig/config.yml)."""
    return get_sprig_home() / "config.yml"
