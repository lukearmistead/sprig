"""Tests for transaction export functionality."""

import csv
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch


from sprig.export import export_transactions_to_csv


def test_export_transactions_to_csv_with_data():
    """Test CSV export with mock transaction data."""
    # Mock transaction data (SQLite row format)
    mock_transactions = [
        ('txn_1', 'acc_1', -25.50, 'Coffee Shop', '2024-01-01', 'debit', 'posted', None, 100.50, None, 'dining', '2024-01-01 10:00:00'),
        ('txn_2', 'acc_1', -45.00, 'Gas Station', '2024-01-02', 'debit', 'posted', None, 55.50, None, 'fuel', '2024-01-02 15:30:00'),
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
                
                # Check header
                expected_header = [
                    'id', 'account_id', 'amount', 'description', 'date', 
                    'type', 'status', 'details', 'running_balance', 'links', 
                    'inferred_category', 'created_at'
                ]
                assert rows[0] == expected_header
                
                # Check data rows
                assert len(rows) == 3  # header + 2 data rows
                assert rows[1][0] == 'txn_1'  # id
                assert rows[1][3] == 'Coffee Shop'  # description
                assert rows[2][0] == 'txn_2'  # id
                assert rows[2][3] == 'Gas Station'  # description


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
    """Test CSV export with default filename."""
    mock_transactions = [
        ('txn_1', 'acc_1', -25.50, 'Coffee Shop', '2024-01-01', 'debit', 'posted', None, 100.50, None, 'dining', '2024-01-01 10:00:00'),
    ]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = Path(temp_dir) / "test.db"
        
        # Change to temp directory to test exports/ creation
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(temp_dir)
            
            # Mock the database
            with patch('sprig.export.SprigDatabase') as mock_db_class:
                mock_db = Mock()
                mock_db.get_transactions_for_export.return_value = mock_transactions
                mock_db_class.return_value = mock_db
                
                # Test export with default filename
                export_transactions_to_csv(temp_db_path)
                
                # Verify exports directory was created
                exports_dir = Path(temp_dir) / "exports"
                assert exports_dir.exists()
                assert exports_dir.is_dir()
                
                # Verify CSV file exists with date pattern  
                csv_files = list(exports_dir.glob("transactions-*.csv"))
                assert len(csv_files) == 1
                
        finally:
            os.chdir(original_cwd)