#!/usr/bin/env python3
"""
Sprig - Teller.io transaction data collection tool.
"""

import argparse
import getpass
import sys
from pathlib import Path

from pydantic import ValidationError

# Add the sprig package to the path
sys.path.insert(0, str(Path(__file__).parent))

# Import after path setup
from sprig.auth import authenticate
from sprig.export import export_transactions_to_csv
from sprig.logger import get_logger
from sprig.models import SyncParams
from sprig.sync import sync_all_accounts
from sprig.credentials import credentials, Credentials

# Initialize logger
logger = get_logger()


def prompt_for_value(prompt_text: str, secret: bool = False) -> str:
    """Prompt user for a single value."""
    if secret:
        return getpass.getpass(prompt_text).strip()
    return input(prompt_text).strip()


def store_credential(key: str, value: str, required: bool = True) -> bool:
    """Store a credential and handle errors."""
    if not credentials.set(key, value):
        if required:
            logger.error(f"Failed to store {key}")
        return False
    return True


def setup_credentials() -> bool:
    """Prompt for and store all required credentials."""
    logger.info("First-time setup: Please enter your credentials")
    logger.info("=" * 50)

    # Required credentials
    app_id = prompt_for_value("Teller APP_ID (app_xxx): ")
    if not app_id:
        logger.error("APP_ID is required")
        return False

    claude_key = prompt_for_value("Claude API Key (sk-ant-api03-xxx): ", secret=True)
    if not claude_key:
        logger.error("Claude API Key is required")
        return False

    # Optional credentials with defaults
    cert_path = prompt_for_value("Certificate path (e.g., certs/certificate.pem): ") or "certs/certificate.pem"
    key_path = prompt_for_value("Private key path (e.g., certs/private_key.pem): ") or "certs/private_key.pem"

    # Store all credentials
    if not store_credential(Credentials.KEY_APP_ID, app_id):
        return False
    if not store_credential(Credentials.KEY_CLAUDE_API_KEY, claude_key):
        return False

    store_credential(Credentials.KEY_CERT_PATH, cert_path, required=False)
    store_credential(Credentials.KEY_KEY_PATH, key_path, required=False)
    store_credential(Credentials.KEY_ENVIRONMENT, "development", required=False)
    store_credential(Credentials.KEY_DATABASE_PATH, "sprig.db", required=False)

    logger.info("Credentials saved to keyring")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Sprig - Fetch and store Teller.io transaction data"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync transaction data")
    sync_parser.add_argument(
        "--full",
        action="store_true",
        help="Perform full resync of all data"
    )
    sync_parser.add_argument(
        "--recategorize",
        action="store_true",
        help="Clear and recategorize all transactions"
    )
    sync_parser.add_argument(
        "--from-date",
        type=str,
        metavar="YYYY-MM-DD",
        help="Only sync transactions from this date onwards (reduces API costs)"
    )
    sync_parser.add_argument(
        "--batch-size",
        type=int,
        metavar="SIZE",
        default=10,
        help="Number of transactions to categorize per API call (default: 10, lower = gentler on rate limits)"
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export transactions to CSV")
    export_parser.add_argument(
        "-o", "--output",
        help="Output filename (default: exports/transactions_YYYY-MM-DD.csv)"
    )

    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Authenticate with Teller (prompts for credentials on first run)")
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "sync":
        try:
            sync_params = SyncParams(
                recategorize=args.recategorize,
                from_date=args.from_date
            )
        except ValidationError as e:
            logger.error("Invalid sync parameters:")
            for error in e.errors():
                field = error['loc'][0]
                msg = error['msg']
                logger.error(f"  {field}: {msg}")
            sys.exit(1)

        try:
            sync_all_accounts(
                recategorize=sync_params.recategorize,
                from_date=sync_params.from_date,
                batch_size=args.batch_size
            )
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            logger.error("Please run 'sprig auth' to set up credentials.")
            sys.exit(1)
    elif args.command == "export":
        db_path = credentials.get_database_path()
        if not db_path:
            logger.error("Database path not found in keyring")
            logger.error("Please run 'sprig auth' to set up credentials.")
            sys.exit(1)

        project_root = Path(__file__).parent
        export_transactions_to_csv(project_root / db_path.value, args.output)
    elif args.command == "auth":
        app_id = credentials.get(Credentials.KEY_APP_ID)
        if not app_id:
            if not setup_credentials():
                sys.exit(1)
            app_id = credentials.get(Credentials.KEY_APP_ID)

        authenticate(app_id, args.environment, args.port)

if __name__ == "__main__":
    main()