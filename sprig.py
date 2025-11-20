#!/usr/bin/env python3
"""
Sprig - Teller.io transaction data collection tool.
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

# Add the sprig package to the path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables once at startup
load_dotenv()

# Import after path setup and env loading
from sprig.auth import authenticate
from sprig.database import SprigDatabase
from sprig.export import export_transactions_to_csv
from sprig.logger import get_logger
from sprig.models import RuntimeConfig, SyncParams
from sprig.models.category_config import CategoryConfig
from sprig.sync import sync_all_accounts

# Initialize logger
logger = get_logger()


def format_transaction(txn_data):
    """Format a transaction tuple for display.

    Args:
        txn_data: Tuple of (id, date, description, amount, inferred_category,
                           counterparty, account_name, account_subtype, account_last_four)
    """
    txn_id, date, description, amount, category, counterparty, acc_name, acc_subtype, last_four = txn_data

    # Format amount with sign and 2 decimal places
    amount_str = f"${abs(amount):.2f}"
    if amount < 0:
        amount_str = f"-{amount_str}"
    else:
        amount_str = f"+{amount_str}"

    # Truncate description if too long
    desc_display = description[:40] + "..." if len(description) > 40 else description

    # Format category (or show as uncategorized)
    category_display = category if category else "[uncategorized]"

    # Build account info
    account_info = f"{acc_name}"
    if last_four:
        account_info += f" (*{last_four})"

    return f"{txn_id[:12]}... | {date} | {amount_str:>10} | {category_display:>15} | {desc_display:40} | {account_info}"


def list_transactions(db_path: Path, limit: int, category: str = None, uncategorized: bool = False):
    """List recent transactions."""
    db = SprigDatabase(db_path)

    if uncategorized:
        # Get uncategorized transactions
        transactions = db.get_uncategorized_transactions()
        # Limit results
        transactions = transactions[:limit]
        logger.info(f"Showing {len(transactions)} uncategorized transactions:")
    elif category:
        transactions = db.get_recent_transactions(limit=limit, category=category)
        logger.info(f"Showing {len(transactions)} transactions in category '{category}':")
    else:
        transactions = db.get_recent_transactions(limit=limit)
        logger.info(f"Showing {len(transactions)} recent transactions:")

    if not transactions:
        logger.info("No transactions found.")
        return

    # Print header
    print()
    print(f"{'Transaction ID':<16} | {'Date':<10} | {'Amount':>10} | {'Category':>15} | {'Description':<40} | Account")
    print("-" * 130)

    # Print transactions
    for txn in transactions:
        print(format_transaction(txn))

    print()
    logger.info(f"Tip: Use 'sprig override <transaction_id> <category>' to change a category")


def override_transaction_category(db_path: Path, transaction_id: str, category: str):
    """Override the category for a specific transaction."""
    db = SprigDatabase(db_path)

    # Load valid categories
    try:
        category_config = CategoryConfig.load()
        valid_categories = [cat.name for cat in category_config.categories]
    except Exception as e:
        logger.error(f"Failed to load category configuration: {e}")
        sys.exit(1)

    # Validate category
    if category not in valid_categories:
        logger.error(f"Invalid category '{category}'")
        logger.error(f"Valid categories: {', '.join(valid_categories)}")
        sys.exit(1)

    # Get the transaction to show before/after
    transaction = db.get_transaction_by_id(transaction_id)
    if not transaction:
        logger.error(f"Transaction not found: {transaction_id}")
        sys.exit(1)

    # Show current state
    old_category = transaction[4] if transaction[4] else "[uncategorized]"
    logger.info(f"Transaction: {transaction_id}")
    logger.info(f"  Date: {transaction[1]}")
    logger.info(f"  Description: {transaction[2]}")
    logger.info(f"  Amount: ${transaction[3]:.2f}")
    logger.info(f"  Current category: {old_category}")

    # Update the category
    if db.update_transaction_category(transaction_id, category):
        logger.info(f"✓ Category updated: {old_category} → {category}")
    else:
        logger.error(f"Failed to update category for transaction {transaction_id}")
        sys.exit(1)


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
    auth_parser = subparsers.add_parser("auth", help="Authenticate with Teller")
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

    # List command
    list_parser = subparsers.add_parser("list", help="List recent transactions")
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of transactions to show (default: 20)"
    )
    list_parser.add_argument(
        "--category",
        type=str,
        help="Filter by category"
    )
    list_parser.add_argument(
        "--uncategorized",
        action="store_true",
        help="Show only uncategorized transactions"
    )

    # Override command
    override_parser = subparsers.add_parser("override", help="Manually set transaction category")
    override_parser.add_argument(
        "transaction_id",
        help="Transaction ID to update"
    )
    override_parser.add_argument(
        "category",
        help="New category name"
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
            logger.error("Please check your .env file and certificate setup.")
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
            logger.error("Please check your .env file and certificate setup.")
            sys.exit(1)
        export_transactions_to_csv(config.database_path, args.output)
    elif args.command == "auth":
        # Auth command doesn't need full config validation
        authenticate(args.environment, args.port)
    elif args.command == "list":
        # List command only needs database path
        try:
            config = RuntimeConfig.load()
        except Exception as e:
            logger.error(f"Configuration error: {e}")
            logger.error("Please check your .env file.")
            sys.exit(1)
        list_transactions(config.database_path, args.limit, args.category, args.uncategorized)
    elif args.command == "override":
        # Override command needs database and category config
        try:
            config = RuntimeConfig.load()
        except Exception as e:
            logger.error(f"Configuration error: {e}")
            logger.error("Please check your .env file.")
            sys.exit(1)
        override_transaction_category(config.database_path, args.transaction_id, args.category)

if __name__ == "__main__":
    main()