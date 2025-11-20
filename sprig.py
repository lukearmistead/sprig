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
from sprig.export import export_transactions_to_csv
from sprig.logger import get_logger
from sprig.models import RuntimeConfig, SyncParams
from sprig.sync import sync_all_accounts
from sprig import credential_manager

# Initialize logger
logger = get_logger()


def handle_credentials_set():
    """Interactively set credentials in keyring."""
    import getpass

    print("Set Sprig Credentials")
    print("=" * 50)
    print("Enter credentials to store in system keyring.")
    print("Press Enter to skip a credential (keep existing value).\n")

    credentials_to_set = {
        "APP_ID": (credential_manager.KEY_APP_ID, "Teller Application ID (app_xxx)"),
        "ACCESS_TOKENS": (credential_manager.KEY_ACCESS_TOKENS, "Teller Access Tokens (comma-separated)"),
        "CLAUDE_API_KEY": (credential_manager.KEY_CLAUDE_API_KEY, "Claude API Key (sk-ant-api03-xxx)"),
        "CERT_PATH": (credential_manager.KEY_CERT_PATH, "Certificate Path (e.g., certs/certificate.pem)"),
        "KEY_PATH": (credential_manager.KEY_KEY_PATH, "Private Key Path (e.g., certs/private_key.pem)"),
        "DATABASE_PATH": (credential_manager.KEY_DATABASE_PATH, "Database Path (e.g., sprig.db)"),
        "ENVIRONMENT": (credential_manager.KEY_ENVIRONMENT, "Teller Environment (development/production)"),
    }

    for display_name, (key, description) in credentials_to_set.items():
        current = credential_manager.get_credential(key, fallback_to_env=True)
        if current:
            masked = credential_manager.mask_credential(current)
            print(f"\n{description}")
            print(f"Current value: {masked}")
        else:
            print(f"\n{description}")
            print("Current value: <not set>")

        # Use getpass for sensitive credentials
        if "KEY" in display_name or "TOKEN" in display_name:
            value = getpass.getpass(f"New value (or press Enter to skip): ")
        else:
            value = input(f"New value (or press Enter to skip): ")

        if value:
            if credential_manager.set_credential(key, value):
                print(f"✓ {display_name} stored in keyring")
            else:
                print(f"✗ Failed to store {display_name}")

    print("\n✓ Credential setup complete!")


def handle_credentials_migrate():
    """Migrate credentials from .env to keyring."""
    print("Migrating credentials from .env to keyring...")

    # Check if .env file exists
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("✗ .env file not found")
        return

    # Perform migration
    results = credential_manager.migrate_from_env()

    print("\nMigration Results:")
    print("=" * 50)

    for key, success in results.items():
        display_name = key.upper()
        if success:
            print(f"✓ {display_name}")
        else:
            print(f"✗ {display_name} (not found in .env or failed to store)")

    successful = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\nMigrated {successful}/{total} credentials to keyring")

    if successful > 0:
        print("\nNote: Your .env file is still present.")
        print("Consider backing it up and removing it after verifying the migration:")
        print(f"  mv {env_path} {env_path}.backup")


def handle_credentials_show():
    """Show current credentials (masked)."""
    print("Current Sprig Credentials")
    print("=" * 50)

    credentials = credential_manager.get_all_credentials(fallback_to_env=True)

    # Check if using keyring or .env
    if credential_manager.has_keyring_credentials():
        print("Source: System Keyring (with .env fallback)")
    else:
        print("Source: .env file only")

    print()

    display_names = {
        credential_manager.KEY_APP_ID: "APP_ID",
        credential_manager.KEY_ACCESS_TOKENS: "ACCESS_TOKENS",
        credential_manager.KEY_CLAUDE_API_KEY: "CLAUDE_API_KEY",
        credential_manager.KEY_CERT_PATH: "CERT_PATH",
        credential_manager.KEY_KEY_PATH: "KEY_PATH",
        credential_manager.KEY_DATABASE_PATH: "DATABASE_PATH",
        credential_manager.KEY_ENVIRONMENT: "ENVIRONMENT",
    }

    for key, value in credentials.items():
        display_name = display_names.get(key, key.upper())
        masked = credential_manager.mask_credential(value)
        print(f"{display_name:20} {masked}")

    if not credential_manager.has_keyring_credentials():
        print("\nTip: Migrate to keyring for more secure credential storage:")
        print("  sprig credentials migrate")


def handle_credentials_clear():
    """Clear all credentials from keyring."""
    import getpass

    print("Clear All Credentials from Keyring")
    print("=" * 50)
    print("WARNING: This will remove all Sprig credentials from your system keyring.")
    print("Your .env file (if present) will not be affected.")

    confirm = input("\nType 'yes' to confirm: ")

    if confirm.lower() != "yes":
        print("Cancelled.")
        return

    results = credential_manager.clear_all_credentials()

    print("\nClear Results:")
    print("=" * 50)

    for key, success in results.items():
        display_name = key.upper()
        if success:
            print(f"✓ {display_name}")
        else:
            print(f"✗ {display_name} (not found or failed to delete)")

    print("\n✓ Keyring credentials cleared")


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

    # Credentials command
    credentials_parser = subparsers.add_parser("credentials", help="Manage credentials in keyring")
    credentials_subparsers = credentials_parser.add_subparsers(dest="credentials_command", help="Credential management commands")

    # credentials set
    credentials_subparsers.add_parser("set", help="Set credentials interactively")

    # credentials migrate
    credentials_subparsers.add_parser("migrate", help="Migrate credentials from .env to keyring")

    # credentials show
    credentials_subparsers.add_parser("show", help="Show current credentials (masked)")

    # credentials clear
    credentials_subparsers.add_parser("clear", help="Clear all credentials from keyring")

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
    elif args.command == "credentials":
        if not args.credentials_command:
            print("Please specify a credential command: set, migrate, show, or clear")
            print("Use 'sprig credentials --help' for more information")
            return

        if args.credentials_command == "set":
            handle_credentials_set()
        elif args.credentials_command == "migrate":
            handle_credentials_migrate()
        elif args.credentials_command == "show":
            handle_credentials_show()
        elif args.credentials_command == "clear":
            handle_credentials_clear()

if __name__ == "__main__":
    main()