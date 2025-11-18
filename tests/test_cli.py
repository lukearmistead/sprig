"""Tests for sprig CLI functionality."""

import subprocess
import sys



def test_cli_help():
    """Test that CLI help command works."""
    result = subprocess.run([
        sys.executable, "sprig.py", "--help"
    ], capture_output=True, text=True)
    
    assert result.returncode == 0
    assert "Sprig - Fetch and store Teller.io transaction data" in result.stdout
    assert "auth" in result.stdout
    assert "sync" in result.stdout
    assert "export" in result.stdout


def test_sync_help():
    """Test that sync command help shows recategorize option."""
    result = subprocess.run([
        sys.executable, "sprig.py", "sync", "--help"
    ], capture_output=True, text=True)
    
    assert result.returncode == 0
    assert "--recategorize" in result.stdout
    assert "Clear and recategorize all transactions" in result.stdout


def test_sync_with_recategorize_flag():
    """Test that --recategorize flag is accepted by CLI."""
    # Test argument parsing by checking help output includes the flag
    result = subprocess.run([
        sys.executable, "sprig.py", "sync", "--help"
    ], capture_output=True, text=True)
    
    assert result.returncode == 0
    assert "--recategorize" in result.stdout
    assert "Clear and recategorize all transactions" in result.stdout


def test_sync_command_basic_help():
    """Test that sync command help is accessible and well-formed."""
    # Test help to verify sync command exists and basic structure
    result = subprocess.run([
        sys.executable, "sprig.py", "sync", "--help"
    ], capture_output=True, text=True)
    
    assert result.returncode == 0
    assert "sync" in result.stdout


def test_export_command_output_flag():
    """Test that export command accepts output flag."""
    result = subprocess.run([
        sys.executable, "sprig.py", "export", "--help"
    ], capture_output=True, text=True)
    
    assert result.returncode == 0
    assert "export" in result.stdout
    assert "-o" in result.stdout or "--output" in result.stdout


def test_auth_command_port_flag():
    """Test that auth command accepts port flag."""
    result = subprocess.run([
        sys.executable, "sprig.py", "auth", "--help"
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert "auth" in result.stdout
    assert "--port" in result.stdout


def test_sync_from_date_flag():
    """Test that sync command accepts --from-date flag."""
    result = subprocess.run([
        sys.executable, "sprig.py", "sync", "--help"
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert "--from-date" in result.stdout
    assert "YYYY-MM-DD" in result.stdout
    assert "Only sync transactions from this date onwards" in result.stdout