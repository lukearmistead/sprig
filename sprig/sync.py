"""Transaction synchronization logic for Sprig."""

from sprig.categorizer import TransactionCategorizer
from sprig.models import RuntimeConfig, TellerAccount, TellerTransaction
from sprig.database import SprigDatabase
from sprig.teller_client import TellerClient

BATCH_SIZE = 20


def sync_all_accounts(config: RuntimeConfig):
    """Sync accounts and transactions for all access tokens."""
    client = TellerClient(config)
    db = SprigDatabase(config.database_path)
    
    for token in config.access_tokens:
        sync_accounts_for_token(client, db, token)
    
    # Categorize any uncategorized transactions
    categorize_uncategorized_transactions(config, db)


def sync_accounts_for_token(client: TellerClient, db: SprigDatabase, token: str):
    """Sync accounts and their transactions for a single token."""
    accounts = client.get_accounts(token)
    
    for account_data in accounts:
        account = TellerAccount(**account_data)
        db.insert_record("accounts", account.model_dump())
        sync_transactions_for_account(client, db, token, account.id)


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
        return
    
    # Process in batches
    for i in range(0, len(transactions), BATCH_SIZE):
        batch = transactions[i:i + BATCH_SIZE]
        categories = categorizer.categorize_batch(batch)
        
        for txn_id, category in categories.items():
            db.update_transaction_category(txn_id, category)