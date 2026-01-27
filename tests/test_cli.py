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
    assert "fetch" in result.stdout
    assert "categorize" in result.stdout


def test_fetch_command_exists():
    """Test that fetch command exists and accepts help flag."""
    result = subprocess.run([
        sys.executable, "sprig.py", "fetch", "--help"
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert "usage: sprig.py fetch" in result.stdout


def test_categorize_command_exists():
    """Test that categorize command exists and accepts help flag."""
    result = subprocess.run([
        sys.executable, "sprig.py", "categorize", "--help"
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert "usage: sprig.py categorize" in result.stdout


def test_sync_command_exists():
    """Test that sync command exists and accepts help flag."""
    result = subprocess.run([
        sys.executable, "sprig.py", "sync", "--help"
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert "usage: sprig.py sync" in result.stdout


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
