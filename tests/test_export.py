"""Tests for transaction export functionality."""

import csv
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch


from sprig.export import export_transactions_to_csv


def test_export_transactions_to_csv_with_data():
    """Test CSV export with mock transaction data (10-field format)."""
    # Mock transaction data (SQLite row format with JOINed account data)
    # Format: id, date, description, amount, inferred_category, confidence, counterparty, account_name, account_subtype, account_last_four
    mock_transactions = [
        ('txn_1', '2024-01-01', 'Coffee Shop', -25.50, 'dining', 0.95, 'Coffee Shop Inc', 'Checking', 'checking', '1234'),
        ('txn_2', '2024-01-02', 'Gas Station', -45.00, 'transport', 0.87, 'Shell Gas', 'Checking', 'checking', '1234'),
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = Path(temp_dir) / "test.db"
        output_path = Path(temp_dir) / "test_export.csv"

        # Mock the database
        with patch('sprig.export.SprigDatabase') as mock_db_class:
            mock_db = Mock()
            mock_db.get_transactions_for_export.return_value = mock_transactions
            mock_db_class.return_value = mock_db

            # Test export
            export_transactions_to_csv(temp_db_path, output_path)

            # Verify database was called correctly
            mock_db_class.assert_called_once_with(temp_db_path)
            mock_db.get_transactions_for_export.assert_called_once()

            # Verify CSV file was created and has correct content
            assert output_path.exists()

            with open(output_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)

                # Check header (10-field format including confidence)
                expected_header = [
                    'id', 'date', 'description', 'amount', 'inferred_category', 'confidence',
                    'counterparty', 'account_name', 'account_subtype', 'account_last_four'
                ]
                assert rows[0] == expected_header

                # Check data rows
                assert len(rows) == 3  # header + 2 data rows
                assert rows[1][0] == 'txn_1'  # id
                assert rows[1][2] == 'Coffee Shop'  # description
                assert rows[2][0] == 'txn_2'  # id
                assert rows[2][2] == 'Gas Station'  # description


def test_export_transactions_to_csv_no_data():
    """Test CSV export with no transaction data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = Path(temp_dir) / "test.db"
        output_path = Path(temp_dir) / "test_export.csv"
        
        # Mock the database with no transactions
        with patch('sprig.export.SprigDatabase') as mock_db_class:
            mock_db = Mock()
            mock_db.get_transactions_for_export.return_value = []
            mock_db_class.return_value = mock_db
            
            # Test export
            export_transactions_to_csv(temp_db_path, output_path)
            
            # Verify no CSV file was created
            assert not output_path.exists()


def test_export_transactions_to_csv_default_filename():
    """Test CSV export with default filename uses ~/.sprig/exports/."""
    # Mock transaction data (new 10-field format)
    mock_transactions = [
        ('txn_1', '2024-01-01', 'Coffee Shop', -25.50, 'dining', 0.95, 'Coffee Shop Inc', 'Checking', 'checking', '1234'),
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = Path(temp_dir) / "test.db"
        temp_exports_dir = Path(temp_dir) / "exports"
        temp_exports_dir.mkdir()  # Create the directory since mock won't

        # Mock the database and the exports directory
        with patch('sprig.export.SprigDatabase') as mock_db_class, \
             patch('sprig.export.get_default_exports_dir', return_value=temp_exports_dir):
            mock_db = Mock()
            mock_db.get_transactions_for_export.return_value = mock_transactions
            mock_db_class.return_value = mock_db

            # Test export with default filename
            export_transactions_to_csv(temp_db_path)

            # Verify exports directory exists
            assert temp_exports_dir.exists()
            assert temp_exports_dir.is_dir()

            # Verify CSV file exists with date pattern
            csv_files = list(temp_exports_dir.glob("transactions-*.csv"))
            assert len(csv_files) == 1