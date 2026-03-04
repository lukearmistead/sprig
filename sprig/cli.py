"""Sprig CLI — single command that guides users through setup."""

import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version

from sprig.auth import authenticate
from sprig.logger import get_logger
from sprig.models.config import load_config
from sprig.paths import get_default_certs_dir, get_default_config_path
from sprig.pipeline import run_pipeline

logger = get_logger()


def open_config(config_path: str):
    """Open config file in default editor."""
    if sys.platform == "darwin":
        subprocess.run(["open", config_path])
    elif sys.platform == "win32":
        os.startfile(config_path)
    else:
        subprocess.run(["xdg-open", config_path])


def main():
    if "--version" in sys.argv:
        try:
            current_version = version("sprig")
        except PackageNotFoundError:
            current_version = "0.0.0-unknown"
        print(f"sprig {current_version}")
        return

    config = load_config()

    # Check credentials - open config if missing
    missing = []
    if not config.teller_app_id:
        missing.append("teller_app_id")
    if not config.claude_key:
        missing.append("claude_key")

    if missing:
        config_path = get_default_config_path()
        certs_dir = get_default_certs_dir()
        print(f"Missing: {', '.join(missing)}")
        print(f"\n1. Add your API keys to {config_path}")
        print(f"2. Download your certificate from Teller (Settings → Certificates)")
        print(f"   Teller downloads it as teller.zip — unzip it, then drag")
        print(f"   certificate.pem and private_key.pem into: {certs_dir}")
        open_config(str(config_path))
        open_config(str(certs_dir))
        while missing:
            input("\nPress Enter when ready...")
            config = load_config()
            missing = []
            if not config.teller_app_id:
                missing.append("teller_app_id")
            if not config.claude_key:
                missing.append("claude_key")
            if missing:
                print(f"Still missing: {', '.join(missing)}")

    # Check accounts - run connect flow if none
    while not config.access_tokens:
        print("No accounts connected. Opening browser to connect...\n")
        authenticate(config)
        config = load_config()
        if not config.access_tokens:
            input("No accounts were connected. Press Enter to try again...")

    # Offer to add more accounts before syncing
    try:
        while input("\nAdd another bank account? [y/N] ").strip().lower() == "y":
            authenticate(config)
            config = load_config()
    except EOFError:
        pass  # Non-interactive mode

    # Run sync
    run_pipeline(config)


if __name__ == "__main__":
    main()
