"""Path utilities for Sprig home directory."""

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_sprig_home() -> Path:
    """Get Sprig home directory, creating it if needed.

    PyInstaller binary: ~/Documents/Sprig/
    Running from source: ~/.sprig/
    """
    if _is_frozen():
        home = Path.home() / "Documents" / "Sprig"
    else:
        home = Path.home() / ".sprig"
    home.mkdir(parents=True, exist_ok=True)
    return home


def get_default_db_path() -> Path:
    return get_sprig_home() / "sprig.db"


def get_default_certs_dir() -> Path:
    certs_dir = get_sprig_home() / "certs"
    certs_dir.mkdir(parents=True, exist_ok=True)
    return certs_dir


def get_default_exports_dir() -> Path:
    exports_dir = get_sprig_home() / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    return exports_dir


def get_default_config_path() -> Path:
    return get_sprig_home() / "config.yml"
