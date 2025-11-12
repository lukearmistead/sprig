#!/usr/bin/env python3
"""
Sprig - Teller.io transaction data collection tool.
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add the sprig package to the path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables once at startup
load_dotenv()

# Import after path setup and env loading
from sprig.auth import authenticate
from sprig.export import export_transactions_to_csv
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
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "sync":
        # Load and validate full configuration for sync
        try:
            config = RuntimeConfig.load()
        except Exception as e:
            print(f"Configuration error: {e}")
            print("Please check your .env file and certificate setup.")
            sys.exit(1)
        sync_all_accounts(config)
    elif args.command == "export":
        # Load and validate full configuration for export
        try:
            config = RuntimeConfig.load()
        except Exception as e:
            print(f"Configuration error: {e}")
            print("Please check your .env file and certificate setup.")
            sys.exit(1)
        export_transactions_to_csv(config.database_path, args.output)
    elif args.command == "auth":
        # Auth command doesn't need full config validation
        authenticate(args.environment, args.port)

if __name__ == "__main__":
    main()