#!/usr/bin/env python3
"""Sprig CLI - Teller.io transaction data collection tool."""

import argparse
import sys
from pathlib import Path

from sprig.auth import authenticate
from sprig.categorize import categorize_uncategorized_transactions
from sprig.database import SprigDatabase
from sprig.export import export_transactions_to_csv
from sprig.logger import get_logger
from sprig.models.config import Config
from sprig.fetch import Fetcher
from sprig.teller_client import TellerClient
import sprig.credentials as credentials

logger = get_logger()


def exit_with_auth_error(message: str) -> None:
    """Exit with error message and auth instruction."""
    logger.error(message)
    logger.error("Please run 'sprig auth' to set up credentials.")
    sys.exit(1)


def setup_credentials() -> bool:
    """Setup or update credentials."""
    logger.info("Sprig credential setup")
    logger.info("=" * 25)

    current_app_id = credentials.get_app_id()
    current_claude_key = credentials.get_claude_api_key()

    current_app_id_str = current_app_id.value if current_app_id else None
    current_claude_key_str = current_claude_key.value if current_claude_key else None

    app_id_prompt = f"Teller APP_ID (current: {current_app_id_str or 'none'}): " if current_app_id_str else "Teller APP_ID (app_xxx): "
    claude_key_prompt = f"Claude API Key (current: {credentials.mask(current_claude_key_str, 12)}): " if current_claude_key_str else "Claude API Key (sk-ant-api03-xxx): "

    app_id = input(app_id_prompt).strip() or current_app_id_str
    claude_key = input(claude_key_prompt).strip() or current_claude_key_str

    if not app_id:
        logger.error("Teller APP_ID is required")
        return False
    if not claude_key:
        logger.error("Claude API key is required")
        return False

    credentials.set_app_id(app_id)
    credentials.set_claude_api_key(claude_key)

    defaults = [
        (credentials.get_cert_path, credentials.set_cert_path, "certs/certificate.pem"),
        (credentials.get_key_path, credentials.set_key_path, "certs/private_key.pem"),
        (credentials.get_environment, credentials.set_environment, "development"),
    ]

    for get_func, set_func, default_value in defaults:
        if not get_func():
            set_func(default_value)

    credentials.get_sprig_home()
    credentials.get_default_certs_dir()

    logger.info("Credentials updated successfully")
    return True


def get_db() -> SprigDatabase:
    """Get database instance from configured path."""
    db_path = credentials.get_database_path()
    if db_path:
        path = Path(db_path.value)
        full_path = path if path.is_absolute() else credentials.get_sprig_home() / db_path.value
    else:
        full_path = credentials.get_default_db_path()
    return SprigDatabase(full_path)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Sprig - Fetch and store Teller.io transaction data"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("fetch", help="Fetch accounts and transactions from Teller")
    subparsers.add_parser("categorize", help="Categorize uncategorized transactions using Claude")
    subparsers.add_parser("sync", help="Pull from Teller, categorize, and export")

    export_parser = subparsers.add_parser("export", help="Export transactions to CSV")
    export_parser.add_argument(
        "-o", "--output",
        help="Output filename (default: ~/.sprig/exports/transactions_YYYY-MM-DD.csv)"
    )

    auth_parser = subparsers.add_parser("auth", help="Setup credentials and authenticate with Teller")
    auth_parser.add_argument(
        "--environment",
        choices=["sandbox", "development", "production"],
        default="development",
        help="Teller environment (default: development)"
    )
    auth_parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Local server port (default: 8001)"
    )

    return parser


def cmd_fetch():
    """Fetch accounts and transactions from Teller."""
    config = Config.load()
    logger.info("Fetching accounts and transactions from Teller")
    if config.from_date:
        logger.info(f"Filtering transactions from {config.from_date}")
    db = get_db()
    fetcher = Fetcher(TellerClient(), db, from_date=config.from_date)
    fetcher.fetch_all()


def cmd_categorize():
    """Categorize uncategorized transactions using Claude."""
    config = Config.load()
    logger.info("Categorizing uncategorized transactions")
    db = get_db()
    categorize_uncategorized_transactions(db, config.batch_size)


def cmd_export(output: str = None):
    """Export transactions to CSV."""
    db_path = credentials.get_database_path()
    if db_path:
        path = Path(db_path.value)
        full_path = path if path.is_absolute() else credentials.get_sprig_home() / db_path.value
    else:
        full_path = credentials.get_default_db_path()
    export_transactions_to_csv(full_path, output)


def cmd_auth(environment: str, port: int):
    """Setup credentials and authenticate with Teller."""
    if not setup_credentials():
        sys.exit(1)
    app_id = credentials.get_app_id()
    authenticate(app_id.value if app_id else None, environment, port)


def cmd_sync():
    """Fetch from Teller, categorize, and export."""
    cmd_fetch()
    cmd_categorize()
    cmd_export()


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "fetch": cmd_fetch,
        "categorize": cmd_categorize,
        "sync": cmd_sync,
        "export": lambda: cmd_export(args.output),
        "auth": lambda: cmd_auth(args.environment, args.port),
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
