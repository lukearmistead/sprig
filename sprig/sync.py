"""Transaction synchronization logic for Sprig."""

from datetime import date
from typing import Optional
import requests

from sprig.categorizer import TransactionCategorizer
from sprig.logger import get_logger
from sprig.models import RuntimeConfig, TellerAccount, TellerTransaction
from sprig.models.category_config import CategoryConfig
from sprig.database import SprigDatabase
from sprig.teller_client import TellerClient

logger = get_logger("sprig.sync")
BATCH_SIZE = 10  # Reduced from 20 to be gentler on API rate limits


def sync_all_accounts(
    config: RuntimeConfig,
    recategorize: bool = False,
    from_date: Optional[date] = None,
    batch_size: int = 10
):
    """Sync accounts and transactions for all access tokens.

    Args:
        config: Runtime configuration
        recategorize: Clear all existing categories before syncing
        from_date: Only sync transactions from this date onwards (reduces API costs)
        batch_size: Number of transactions to categorize per API call (default: 10)
    """
    logger.info(f"Starting sync for {len(config.access_tokens)} access token(s)")

    client = TellerClient(config)
    db = SprigDatabase(config.database_path)

    # Use from_date if specified
    cutoff_date = from_date
    if from_date:
        logger.info(f"Filtering transactions from {from_date}")

    # Clear all categories if recategorizing
    if recategorize:
        rows_cleared = db.clear_all_categories()
        logger.info(f"Cleared categories for {rows_cleared} transaction(s)")

    invalid_tokens = []
    valid_tokens = 0

    for i, token_obj in enumerate(config.access_tokens, 1):
        logger.debug(f"Processing token {i}/{len(config.access_tokens)}")
        success = sync_accounts_for_token(client, db, token_obj.token, cutoff_date)
        if success:
            valid_tokens += 1
        else:
            invalid_tokens.append(token_obj.token[:12] + "...")  # Show partial token for identification

    if invalid_tokens:
        logger.warning(f"\nFound {len(invalid_tokens)} invalid/expired token(s):")
        for token in invalid_tokens:
            logger.warning(f"   - {token}")
        logger.warning("These may be from re-authenticated accounts. Consider removing them from ACCESS_TOKENS in .env")

    logger.info(f"Successfully synced {valid_tokens} valid token(s)")

    # Categorize any uncategorized transactions
    try:
        categorize_uncategorized_transactions(config, db, batch_size)
    except Exception as e:
        if "rate_limit_error" in str(e) or "rate limit" in str(e).lower():
            logger.error("Categorization stopped due to Claude API rate limits")
            logger.info("Your transactions have been synced - categorization can be resumed later")
            logger.info("Run 'python sprig.py sync' again in a few minutes to continue categorization")
            logger.info("Or use 'python sprig.py sync --from-date YYYY-MM-DD' to categorize recent transactions only")
        else:
            logger.error(f"Categorization failed: {e}")
            logger.info("Your transactions have been synced successfully - only categorization was affected")


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


def categorize_uncategorized_transactions(runtime_config: RuntimeConfig, db: SprigDatabase, batch_size: int = 10, category_config: CategoryConfig = None):
    """Categorize transactions that don't have an inferred_category assigned."""
    logger.debug("Starting categorization function")

    # Load category config to get manual overrides
    if category_config is None:
        category_config = CategoryConfig.load()
    manual_override_map = {override.transaction_id: override.category
                          for override in category_config.manual_overrides}

    uncategorized = db.get_uncategorized_transactions()
    logger.debug(f"Database returned {len(uncategorized)} uncategorized transaction rows")

    # Apply manual overrides first
    manual_override_count = 0
    if manual_override_map:
        logger.info(f"Applying {len(manual_override_map)} manual category override(s) from config.yml")
        for row in uncategorized:
            txn_id = row[0]
            if txn_id in manual_override_map:
                category = manual_override_map[txn_id]
                db.update_transaction_category(txn_id, category)
                manual_override_count += 1
                logger.debug(f"   Applied manual override: {txn_id} → {category}")

        if manual_override_count > 0:
            logger.info(f"   Applied {manual_override_count} manual override(s)")

        # Refresh uncategorized list after applying manual overrides
        uncategorized = db.get_uncategorized_transactions()

    # Convert remaining uncategorized to TellerTransaction objects with account info
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
            "counterparty": row[8],  # counterparty from JSON extraction
            "last_four": row[9]  # account last four digits
        }

    if not transactions:
        if manual_override_count > 0:
            logger.info("All remaining transactions have been manually overridden - no Claude categorization needed!")
        else:
            logger.info("No uncategorized transactions found - all transactions already have categories!")
        return

    categorizer = TransactionCategorizer(runtime_config)

    total_transactions = len(transactions)
    logger.debug(f"Converted to {total_transactions} TellerTransaction objects")
    total_batches = (total_transactions + batch_size - 1) // batch_size
    categorized_count = 0
    failed_count = 0

    logger.info(f"Categorizing {total_transactions} uncategorized transaction(s) using Claude AI")
    logger.info(f"   Processing in {total_batches} batch(es) of up to {batch_size} transactions each")

    if total_transactions > 100:
        logger.info("   Large transaction volume may hit Claude API rate limits")
        logger.info("   Consider using '--from-date YYYY-MM-DD' flag to process recent transactions first")

    # Process in batches
    for i in range(0, len(transactions), batch_size):
        batch = transactions[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        logger.info(f"   Processing batch {batch_num}/{total_batches} ({len(batch)} transactions)...")
        
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
            logger.info(f"      Batch {batch_num} complete: {batch_success_count} categorized")
        else:
            logger.warning(f"      Batch {batch_num} partial: {batch_success_count}/{len(batch)} categorized")

    # Show final summary
    logger.info("Categorization complete")
    logger.info(f"   Successfully categorized: {categorized_count} transactions")
    if failed_count > 0:
        logger.warning(f"   Failed to categorize: {failed_count} transactions")
    logger.info(f"   Success rate: {(categorized_count / total_transactions * 100):.1f}%")