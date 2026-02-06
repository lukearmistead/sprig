"""Sprig CLI — single command that guides users through setup."""

import os
import subprocess
import sys

from sprig.auth import authenticate
from sprig.categorize import categorize_uncategorized_transactions
from sprig.database import SprigDatabase
from sprig.export import export_transactions_to_csv
from sprig.fetch import Fetcher
from sprig.logger import get_logger
from sprig.models.config import Config
from sprig.paths import get_default_certs_dir, get_default_config_path, get_default_db_path, resolve_cert_path
from sprig.teller_client import TellerClient

logger = get_logger()


def open_config(config_path: str):
    """Open config file in default editor."""
    if sys.platform == "darwin":
        subprocess.run(["open", config_path])
    elif sys.platform == "win32":
        os.startfile(config_path)
    else:
        subprocess.run(["xdg-open", config_path])


def run_sync(config: Config):
    """Fetch, categorize, and export transactions."""
    db_path = get_default_db_path()
    db = SprigDatabase(db_path)

    logger.info("Fetching transactions from Teller")
    if config.from_date:
        logger.info(f"Filtering transactions from {config.from_date}")
    client = TellerClient(resolve_cert_path(config.cert_path), resolve_cert_path(config.key_path))
    fetcher = Fetcher(client, db, config.access_tokens, from_date=config.from_date)
    fetcher.fetch_all()

    logger.info("Categorizing transactions")
    categorize_uncategorized_transactions(db, config)

    logger.info("Exporting to CSV")
    export_transactions_to_csv(db_path)


def main():
    config = Config.load()

    # Check credentials - open config if missing
    missing = []
    if not config.app_id:
        missing.append("app_id")
    if not config.claude_key:
        missing.append("claude_key")

    if missing:
        config_path = get_default_config_path()
        certs_dir = get_default_certs_dir()
        print(f"Missing: {', '.join(missing)}")
        print(f"\n1. Add your API keys to {config_path}")
        print(f"2. Download your Teller certificate and key into {certs_dir}")
        open_config(str(config_path))
        open_config(str(certs_dir))
        while missing:
            input("\nPress Enter when ready...")
            config = Config.load()
            missing = []
            if not config.app_id:
                missing.append("app_id")
            if not config.claude_key:
                missing.append("claude_key")
            if missing:
                print(f"Still missing: {', '.join(missing)}")

    # Check accounts - run connect flow if none
    while not config.access_tokens:
        print("No accounts connected. Opening browser to connect...\n")
        authenticate(config)
        config = Config.load()
        if not config.access_tokens:
            input("No accounts were connected. Press Enter to try again...")

    # Run sync
    run_sync(config)

    # Offer to add more accounts
    try:
        response = input("\nAdd another bank account? [y/N] ").strip().lower()
        if response == "y":
            authenticate(config)
    except EOFError:
        pass  # Non-interactive mode


if __name__ == "__main__":
    main()
