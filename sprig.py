#!/usr/bin/env python3
"""
Sprig - Teller.io transaction data collection tool.
"""

import argparse
import sys
from pathlib import Path

# Add the sprig package to the path
sys.path.insert(0, str(Path(__file__).parent))

from sprig.models import RuntimeConfig
from sprig.sync import sync_all_accounts

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
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Load and validate configuration
    try:
        config = RuntimeConfig.load()
    except Exception as e:
        print(f"Configuration error: {e}")
        print("Please check your .env file and certificate setup.")
        sys.exit(1)
    
    if args.command == "sync":
        sync_all_accounts(config)

if __name__ == "__main__":
    main()