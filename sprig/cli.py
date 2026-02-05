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
from sprig.paths import get_default_config_path, get_default_db_path, resolve_cert_path
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
        print("Config needs your API keys. Opening config.yml...\n")
        print(f"Missing: {', '.join(missing)}")
        print("\nFill in the values, save, then run Sprig again.")
        open_config(str(get_default_config_path()))
        return

    # Check accounts - run connect flow if none
    if not config.access_tokens:
        print("No accounts connected. Opening browser to connect...\n")
        authenticate(config)
        config = Config.load()  # Reload after connect
        if not config.access_tokens:
            print("No accounts were connected. Run Sprig again when ready.")
            return

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
