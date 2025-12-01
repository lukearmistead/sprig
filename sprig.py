#!/usr/bin/env python3
"""
Sprig - Teller.io transaction data collection tool.
"""

import argparse
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
import sprig.credentials as credentials

# Initialize logger
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

    # Get current credential values
    current_app_id = credentials.get_app_id()
    current_claude_key = credentials.get_claude_api_key()
    
    current_app_id_str = current_app_id.value if current_app_id else None
    current_claude_key_str = current_claude_key.value if current_claude_key else None

    # Prompt with current values shown
    app_id_prompt = f"Teller APP_ID (current: {current_app_id_str or 'none'}): " if current_app_id_str else "Teller APP_ID (app_xxx): "
    claude_key_prompt = f"Claude API Key (current: {credentials.mask(current_claude_key_str, 12)}): " if current_claude_key_str else "Claude API Key (sk-ant-api03-xxx): "

    app_id = input(app_id_prompt).strip() or current_app_id_str
    claude_key = input(claude_key_prompt).strip() or current_claude_key_str

    # Validate and store using clean interfaces
    if not app_id:
        logger.error("Teller APP_ID is required")
        return False
    if not claude_key:
        logger.error("Claude API key is required")
        return False

    credentials.set_app_id(app_id)
    credentials.set_claude_api_key(claude_key)

    # Set defaults for other credentials if not already set
    defaults = [
        (credentials.get_cert_path, credentials.set_cert_path, "certs/certificate.pem"),
        (credentials.get_key_path, credentials.set_key_path, "certs/private_key.pem"),
        (credentials.get_environment, credentials.set_environment, "development"),
        (credentials.get_database_path, credentials.set_database_path, "sprig.db"),
    ]
    
    for get_func, set_func, default_value in defaults:
        if not get_func():
            set_func(default_value)

    logger.info("Credentials updated successfully")
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
                batch_size=args.batch_size,
                full=args.full
            )
        except ValueError as e:
            exit_with_auth_error(f"Configuration error: {e}")
    elif args.command == "export":
        db_path = credentials.get_database_path()
        if not db_path:
            exit_with_auth_error("Database path not found in keyring")

        project_root = Path(__file__).parent
        export_transactions_to_csv(project_root / db_path.value, args.output)
    elif args.command == "auth":
        if not setup_credentials():
            sys.exit(1)
            
        app_id = credentials.get_app_id()
        authenticate(app_id.value if app_id else None, args.environment, args.port)

if __name__ == "__main__":
    main()