"""Transaction export functionality for Sprig."""

import csv
from datetime import datetime
from pathlib import Path

from sprig.database import SprigDatabase
from sprig.logger import get_logger

logger = get_logger("sprig.export")


def export_transactions_to_csv(database_path, output_path=None):
    """Export all transactions to CSV file."""
    if output_path is None:
        # Create exports directory if it doesn't exist
        exports_dir = Path("exports")
        exports_dir.mkdir(exist_ok=True)
        output_path = exports_dir / f"transactions-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.csv"

    logger.info(f"Starting export to {output_path}")

    db = SprigDatabase(database_path)
    transactions = db.get_transactions_for_export()

    if not transactions:
        logger.warning("No transactions found to export.")
        return

    # Column names matching the 10-field export query
    column_names = [
        'id', 'date', 'description', 'amount', 'inferred_category', 'confidence',
        'counterparty', 'account_name', 'account_subtype', 'account_last_four'
    ]

    logger.debug(f"Exporting {len(transactions)} transaction(s) with {len(column_names)} columns")

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Write header
        writer.writerow(column_names)

        # Write transaction data
        for transaction in transactions:
            writer.writerow(transaction)

    logger.info(f"Exported {len(transactions)} transaction(s) to {output_path}")
