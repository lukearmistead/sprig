"""Tests for sprig CLI functionality."""

import subprocess
import sys


def test_cli_help():
    result = subprocess.run([
        sys.executable, "-m", "sprig", "--help"
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert "Sprig" in result.stdout
    assert "connect" in result.stdout
    assert "sync" in result.stdout


def test_connect_command_exists():
    result = subprocess.run([
        sys.executable, "-m", "sprig", "connect", "--help"
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert "connect" in result.stdout


def test_sync_command_exists():
    result = subprocess.run([
        sys.executable, "-m", "sprig", "sync", "--help"
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert "sync" in result.stdout


def test_no_command_prints_help():
    result = subprocess.run([
        sys.executable, "-m", "sprig"
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert "connect" in result.stdout
    assert "sync" in result.stdout
