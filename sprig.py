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
from sprig.models import RuntimeConfig, SyncParams
from sprig.sync import sync_all_accounts

# Initialize logger
logger = get_logger()


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
        # Load and validate full configuration for sync
        try:
            config = RuntimeConfig.load()
        except Exception as e:
            logger.error(f"Configuration error: {e}")
            logger.error("Please run 'sprig auth' to set up credentials.")
            sys.exit(1)

        # Validate sync parameters with Pydantic
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

        sync_all_accounts(
            config,
            recategorize=sync_params.recategorize,
            from_date=sync_params.from_date,
            batch_size=args.batch_size
        )
    elif args.command == "export":
        # Load and validate full configuration for export
        try:
            config = RuntimeConfig.load()
        except Exception as e:
            logger.error(f"Configuration error: {e}")
            logger.error("Please run 'sprig auth' to set up credentials.")
            sys.exit(1)
        export_transactions_to_csv(config.database_path, args.output)
    elif args.command == "auth":
        authenticate(args.environment, args.port)

if __name__ == "__main__":
    main()