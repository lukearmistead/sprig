"""Sprig CLI — single command that guides users through setup."""

import sys
from importlib.metadata import PackageNotFoundError, version

from sprig.auth import authenticate
from sprig.logger import get_logger
from sprig.models.config import load_config
from sprig.pipeline import run_pipeline

logger = get_logger()


def main():
    if "--version" in sys.argv:
        try:
            current_version = version("sprig")
        except PackageNotFoundError:
            current_version = "0.0.0-unknown"
        print(f"sprig {current_version}")
        return

    config = load_config()

    if not config.claude_key:
        print("No API key -- transactions will be downloaded from Teller without categorizing")

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
