"""Sprig CLI — two commands, one config file."""

import argparse
import sys
from pathlib import Path

from sprig.auth import authenticate
from sprig.categorize import categorize_uncategorized_transactions
from sprig.database import SprigDatabase
from sprig.export import export_transactions_to_csv
from sprig.fetch import Fetcher
from sprig.logger import get_logger
from sprig.models.config import Config
from sprig.paths import get_default_db_path, get_sprig_home
from sprig.teller_client import TellerClient

logger = get_logger()


def resolve_cert_paths(config: Config) -> tuple[str, str]:
    """Resolve cert/key paths relative to sprig home."""
    home = get_sprig_home()
    cert = Path(config.cert_path)
    key = Path(config.key_path)
    cert_resolved = str(cert if cert.is_absolute() else home / cert)
    key_resolved = str(key if key.is_absolute() else home / key)
    return cert_resolved, key_resolved


def cmd_connect(config: Config):
    if not config.app_id:
        logger.error("Set app_id in config.yml before connecting.")
        sys.exit(1)
    authenticate(config)


def cmd_sync(config: Config):
    missing = []
    if not config.app_id:
        missing.append("app_id")
    if not config.claude_key:
        missing.append("claude_key")
    if not config.access_tokens:
        missing.append("access_tokens (run `sprig connect` first)")
    if missing:
        logger.error(f"Missing config: {', '.join(missing)}")
        sys.exit(1)

    db_path = get_default_db_path()
    db = SprigDatabase(db_path)
    cert_path, key_path = resolve_cert_paths(config)

    logger.info("Fetching transactions from Teller")
    if config.from_date:
        logger.info(f"Filtering transactions from {config.from_date}")
    client = TellerClient(cert_path, key_path)
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
