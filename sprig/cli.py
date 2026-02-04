"""Sprig CLI — two commands, one config file."""

import argparse
import sys

from sprig.auth import authenticate
from sprig.categorize import categorize_uncategorized_transactions
from sprig.database import SprigDatabase
from sprig.export import export_transactions_to_csv
from sprig.fetch import Fetcher
from sprig.logger import get_logger
from sprig.models.config import Config
from sprig.paths import get_default_db_path, resolve_cert_path
from sprig.teller_client import TellerClient

logger = get_logger()


def cmd_connect(config: Config):
    if not config.app_id:
        logger.error("Set app_id in config.yml before connecting.")
        sys.exit(1)
    authenticate(config)


def cmd_sync(config: Config):
    if not config.app_id or not config.claude_key or not config.access_tokens:
        logger.error("Missing required config. Set app_id, claude_key, and run `sprig connect`.")
        sys.exit(1)

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sprig — local transaction sync")
    sub = parser.add_subparsers(dest="command", help="Available commands")
    sub.add_parser("connect", help="Connect a bank account via Teller")
    sub.add_parser("sync", help="Fetch, categorize, and export transactions")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    config = Config.load()
    {"connect": cmd_connect, "sync": cmd_sync}[args.command](config)


if __name__ == "__main__":
    main()
