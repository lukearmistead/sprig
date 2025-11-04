"""Transaction export functionality for Sprig."""

import csv
from datetime import datetime
from pathlib import Path

from sprig.database import SprigDatabase


def export_transactions_to_csv(database_path, output_path=None):
    """Export all transactions to CSV file."""
    if output_path is None:
        # Create exports directory if it doesn't exist
        exports_dir = Path("exports")
        exports_dir.mkdir(exist_ok=True)
        output_path = exports_dir / f"transactions-{datetime.now().strftime('%Y-%m-%d')}.csv"

    db = SprigDatabase(database_path)
    transactions = db.get_transactions_for_export()

    if not transactions:
        print("No transactions found to export.")
        return

    # Get column names from database schema
    column_names = [
        'id', 'account_id', 'amount', 'description', 'date',
        'type', 'status', 'details', 'running_balance', 'links',
        'inferred_category', 'created_at'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Write header
        writer.writerow(column_names)

        # Write transaction data
        for transaction in transactions:
            writer.writerow(transaction)

    print(f"Exported {len(transactions)} transactions to {output_path}")
