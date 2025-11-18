"""Transaction synchronization logic for Sprig."""

from datetime import date, timedelta
from typing import Optional
import requests

from sprig.categorizer import TransactionCategorizer
from sprig.logger import get_logger
from sprig.models import RuntimeConfig, TellerAccount, TellerTransaction
from sprig.database import SprigDatabase
from sprig.teller_client import TellerClient

logger = get_logger("sprig.sync")
BATCH_SIZE = 20


def sync_all_accounts(
    config: RuntimeConfig,
    recategorize: bool = False,
    days: Optional[int] = None
):
    """Sync accounts and transactions for all access tokens.

    Args:
        config: Runtime configuration
        recategorize: Clear all existing categories before syncing
        days: Only sync transactions from the last N days (reduces API costs)
    """
    logger.info(f"🔄 Starting sync for {len(config.access_tokens)} access token(s)")

    client = TellerClient(config)
    db = SprigDatabase(config.database_path)

    # Calculate cutoff date if days specified
    cutoff_date = None
    if days:
        cutoff_date = date.today() - timedelta(days=days)
        logger.info(f"Filtering transactions from the last {days} days (since {cutoff_date})")

    # Clear all categories if recategorizing
    if recategorize:
        rows_cleared = db.clear_all_categories()
        logger.info(f"Cleared categories for {rows_cleared} transaction(s)")

    invalid_tokens = []
    valid_tokens = 0

    for i, token in enumerate(config.access_tokens, 1):
        logger.debug(f"Processing token {i}/{len(config.access_tokens)}")
        success = sync_accounts_for_token(client, db, token, cutoff_date)
        if success:
            valid_tokens += 1
        else:
            invalid_tokens.append(token[:12] + "...")  # Show partial token for identification

    if invalid_tokens:
        logger.warning(f"\n⚠️  Found {len(invalid_tokens)} invalid/expired token(s):")
        for token in invalid_tokens:
            logger.warning(f"   - {token}")
        logger.warning("These may be from re-authenticated accounts. Consider removing them from ACCESS_TOKENS in .env")

    logger.info(f"✅ Successfully synced {valid_tokens} valid token(s)")

    # Categorize any uncategorized transactions
    categorize_uncategorized_transactions(config, db)


def sync_accounts_for_token(
    client: TellerClient,
    db: SprigDatabase,
    token: str,
    cutoff_date: Optional[date] = None
) -> bool:
    """Sync accounts and their transactions for a single token.

    Args:
        client: Teller API client
        db: Database instance
        token: Access token
        cutoff_date: Only sync transactions on or after this date

    Returns:
        True if sync was successful, False if token is invalid/expired
    """
    try:
        accounts = client.get_accounts(token)
    except requests.HTTPError as e:
        if e.response and e.response.status_code == 401:
            logger.warning(f"Skipping invalid/expired token {token[:12]}... (account may have been re-authenticated)")
            return False
        else:
            # Re-raise other HTTP errors
            raise

    logger.debug(f"Found {len(accounts)} account(s) for token {token[:12]}...")
    for account_data in accounts:
        account = TellerAccount(**account_data)
        db.insert_record("accounts", account.model_dump())
        sync_transactions_for_account(client, db, token, account.id, cutoff_date)

    return True


def sync_transactions_for_account(
    client: TellerClient,
    db: SprigDatabase,
    token: str,
    account_id: str,
    cutoff_date: Optional[date] = None
):
    """Sync transactions for a specific account.

    Args:
        client: Teller API client
        db: Database instance
        token: Access token
        account_id: Account ID to fetch transactions for
        cutoff_date: Only sync transactions on or after this date
    """
    transactions = client.get_transactions(token, account_id)
    logger.debug(f"Syncing {len(transactions)} transaction(s) for account {account_id}")

    for transaction_data in transactions:
        transaction = TellerTransaction(**transaction_data)

        # Filter by cutoff date if specified
        if cutoff_date and transaction.date < cutoff_date:
            continue

        db.insert_record("transactions", transaction.model_dump())


def categorize_uncategorized_transactions(runtime_config: RuntimeConfig, db: SprigDatabase):
    """Categorize all uncategorized transactions."""
    categorizer = TransactionCategorizer(runtime_config)
    uncategorized = db.get_uncategorized_transactions()
    
    # Convert to TellerTransaction objects with account info
    transactions = []
    account_info = {}
    for row in uncategorized:
        txn_id = row[0]
        txn_data = {
            "id": txn_id, "description": row[1], "amount": row[2], 
            "date": row[3], "type": row[4], "account_id": row[5], 
            "status": "posted"
        }
        transactions.append(TellerTransaction(**txn_data))
        # Store account info and counterparty for later use
        account_info[txn_id] = {
            "name": row[6],
            "subtype": row[7],
            "counterparty": row[8]  # counterparty from JSON extraction
        }
    
    if not transactions:
        logger.debug("No uncategorized transactions found")
        return

    total_transactions = len(transactions)
    total_batches = (total_transactions + BATCH_SIZE - 1) // BATCH_SIZE
    categorized_count = 0
    failed_count = 0

    logger.info(f"🤖 Starting categorization of {total_transactions} transaction(s) in {total_batches} batch(es)")

    # Process in batches
    for i in range(0, len(transactions), BATCH_SIZE):
        batch = transactions[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        
        logger.debug(f"Processing batch {batch_num} of {total_batches} ({len(batch)} transactions)...")
        
        # Get account info for this batch
        batch_account_info = {t.id: account_info[t.id] for t in batch}
        categories = categorizer.categorize_batch(batch, batch_account_info)
        
        # Update database with successful categorizations
        batch_success_count = 0
        for txn_id, category in categories.items():
            db.update_transaction_category(txn_id, category)
            batch_success_count += 1

        categorized_count += batch_success_count
        failed_count += len(batch) - batch_success_count

        if batch_success_count == len(batch):
            logger.debug(f"Batch {batch_num} completed successfully ({batch_success_count} categorized)")
        else:
            logger.warning(f"Batch {batch_num} partially failed ({batch_success_count}/{len(batch)} categorized)")

    # Show final summary
    logger.info(f"✅ Categorization complete:")
    logger.info(f"   Categorized: {categorized_count}")
    if failed_count > 0:
        logger.warning(f"   Failed: {failed_count}")
    logger.info(f"   Success rate: {(categorized_count / total_transactions * 100):.1f}%")