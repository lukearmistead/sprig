"""Transaction synchronization logic for Sprig."""

import requests

from sprig.categorizer import TransactionCategorizer
from sprig.models import RuntimeConfig, TellerAccount, TellerTransaction
from sprig.database import SprigDatabase
from sprig.teller_client import TellerClient

BATCH_SIZE = 20


def sync_all_accounts(config: RuntimeConfig, recategorize: bool = False):
    """Sync accounts and transactions for all access tokens."""
    client = TellerClient(config)
    db = SprigDatabase(config.database_path)
    
    # Clear all categories if recategorizing
    if recategorize:
        rows_cleared = db.clear_all_categories()
        print(f"Cleared categories for {rows_cleared} transactions")
    
    invalid_tokens = []
    valid_tokens = 0
    
    for token in config.access_tokens:
        success = sync_accounts_for_token(client, db, token)
        if success:
            valid_tokens += 1
        else:
            invalid_tokens.append(token[:12] + "...")  # Show partial token for identification
    
    if invalid_tokens:
        print(f"\nFound {len(invalid_tokens)} invalid/expired tokens:")
        for token in invalid_tokens:
            print(f"   - {token}")
        print("These may be from re-authenticated accounts. Consider removing them from ACCESS_TOKENS in .env")
    
    print(f"Successfully synced {valid_tokens} valid tokens")
    
    # Categorize any uncategorized transactions
    categorize_uncategorized_transactions(config, db)


def sync_accounts_for_token(client: TellerClient, db: SprigDatabase, token: str) -> bool:
    """Sync accounts and their transactions for a single token.
    
    Returns:
        True if sync was successful, False if token is invalid/expired
    """
    try:
        accounts = client.get_accounts(token)
    except requests.HTTPError as e:
        if e.response and e.response.status_code == 401:
            print(f"Skipping invalid/expired token {token[:12]}... (account may have been re-authenticated)")
            return False
        else:
            # Re-raise other HTTP errors
            raise
    
    for account_data in accounts:
        account = TellerAccount(**account_data)
        db.insert_record("accounts", account.model_dump())
        sync_transactions_for_account(client, db, token, account.id)
    
    return True


def sync_transactions_for_account(client: TellerClient, db: SprigDatabase, token: str, account_id: str):
    """Sync transactions for a specific account."""
    transactions = client.get_transactions(token, account_id)
    
    for transaction_data in transactions:
        transaction = TellerTransaction(**transaction_data)
        db.insert_record("transactions", transaction.model_dump())


def categorize_uncategorized_transactions(runtime_config: RuntimeConfig, db: SprigDatabase):
    """Categorize all uncategorized transactions."""
    categorizer = TransactionCategorizer(runtime_config)
    uncategorized = db.get_uncategorized_transactions()
    
    # Convert to TellerTransaction objects
    transactions = []
    for row in uncategorized:
        txn_data = {
            "id": row[0], "description": row[1], "amount": row[2], 
            "date": row[3], "type": row[4], "account_id": "unknown", 
            "status": "unknown"
        }
        transactions.append(TellerTransaction(**txn_data))
    
    if not transactions:
        print("No uncategorized transactions found")
        return
    
    total_transactions = len(transactions)
    total_batches = (total_transactions + BATCH_SIZE - 1) // BATCH_SIZE
    categorized_count = 0
    failed_count = 0
    
    print(f"Starting categorization of {total_transactions} transactions in {total_batches} batches")
    
    # Process in batches
    for i in range(0, len(transactions), BATCH_SIZE):
        batch = transactions[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        
        print(f"Processing batch {batch_num} of {total_batches} ({len(batch)} transactions)...")
        
        categories = categorizer.categorize_batch(batch)
        
        # Update database with successful categorizations
        batch_success_count = 0
        for txn_id, category in categories.items():
            db.update_transaction_category(txn_id, category)
            batch_success_count += 1
        
        categorized_count += batch_success_count
        failed_count += len(batch) - batch_success_count
        
        if batch_success_count == len(batch):
            print(f"Batch {batch_num} completed successfully ({batch_success_count} categorized)")
        else:
            print(f"WARNING: Batch {batch_num} partially failed ({batch_success_count}/{len(batch)} categorized)")
    
    # Show final summary
    print("\nCategorization Summary:")
    print(f"   Categorized: {categorized_count}")
    print(f"   Failed: {failed_count}")
    print(f"   Success rate: {(categorized_count / total_transactions * 100):.1f}%")