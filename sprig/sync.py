"""Transaction synchronization logic for Sprig."""

from datetime import date
from typing import Optional
import requests

from sprig.categorizer import ManualCategorizer, ClaudeCategorizer
from sprig.models.category_config import CategoryConfig
from sprig.logger import get_logger
from sprig.models import TellerAccount, TellerTransaction
from sprig.database import SprigDatabase
from sprig.teller_client import TellerClient
import sprig.credentials as credentials

logger = get_logger("sprig.sync")


def sync_all_accounts(
    recategorize: bool = False,
    from_date: Optional[date] = None,
    batch_size: Optional[int] = None,
):
    """Sync accounts and transactions for all access tokens.

    Args:
        recategorize: Clear all existing categories before syncing
        from_date: Only sync transactions from this date onwards (reduces API costs)
        batch_size: Number of transactions to categorize per API call (default: from config.yml)
    """
    access_tokens = credentials.get_access_tokens()
    logger.info(f"Starting sync for {len(access_tokens)} access token(s)")

    client = TellerClient()

    db_path = credentials.get_database_path()
    if not db_path:
        raise ValueError("Database path not found in keyring")

    from pathlib import Path

    project_root = Path(__file__).parent.parent
    db = SprigDatabase(project_root / db_path.value)

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

    for i, token_obj in enumerate(access_tokens, 1):
        logger.debug(f"Processing token {i}/{len(access_tokens)}")
        success = sync_accounts_for_token(client, db, token_obj.token, cutoff_date)
        if success:
            valid_tokens += 1
        else:
            invalid_tokens.append(
                token_obj.token[:12] + "..."
            )  # Show partial token for identification

    if invalid_tokens:
        logger.warning(f"\nFound {len(invalid_tokens)} invalid/expired token(s):")
        for token in invalid_tokens:
            logger.warning(f"   - {token}")
        logger.warning(
            "These may be from re-authenticated accounts. Consider removing them from ACCESS_TOKENS in .env"
        )

    logger.info(f"Successfully synced {valid_tokens} valid token(s)")

    # Categorize any uncategorized transactions
    try:
        category_config = CategoryConfig.load()
        effective_batch_size = (
            batch_size if batch_size is not None else category_config.batch_size
        )
        categorize_uncategorized_transactions(db, effective_batch_size)
    except Exception as e:
        if "rate_limit_error" in str(e) or "rate limit" in str(e).lower():
            logger.error("Categorization stopped due to Claude API rate limits")
            logger.info(
                "Your transactions have been synced - categorization can be resumed later"
            )
            logger.info(
                "Run 'python sprig.py sync' again in a few minutes to continue categorization"
            )
            logger.info(
                "Or use 'python sprig.py sync --from-date YYYY-MM-DD' to categorize recent transactions only"
            )
        else:
            logger.error(f"Categorization failed: {e}")
            logger.info(
                "Your transactions have been synced successfully - only categorization was affected"
            )


def sync_accounts_for_token(
    client: TellerClient,
    db: SprigDatabase,
    token: str,
    cutoff_date: Optional[date] = None,
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
            logger.warning(
                f"Skipping invalid/expired token {token[:12]}... (account may have been re-authenticated)"
            )
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
    cutoff_date: Optional[date] = None,
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

        db.sync_transaction(transaction)


def categorize_uncategorized_transactions(db: SprigDatabase, batch_size: int):
    """Categorize transactions that don't have an inferred_category assigned."""
    logger.debug("Starting categorization function")

    # Initialize categorizers
    category_config = CategoryConfig.load()
    manual_categorizer = ManualCategorizer(category_config)

    # Initialize Claude categorizer (API key is mandatory)
    try:
        claude_categorizer = ClaudeCategorizer(category_config)
    except ValueError as e:
        logger.error(f"Claude API key is required for categorization: {e}")
        logger.error("Please run 'python sprig.py auth' to set up your Claude API key")
        raise ValueError("Claude API key not configured")

    uncategorized = db.get_uncategorized_transactions()
    logger.debug(
        f"Database returned {len(uncategorized)} uncategorized transaction rows"
    )

    # Convert to TellerTransaction objects with account info
    transactions = []
    account_info = {}
    for row in uncategorized:
        txn_id = row[0]
        txn_data = {
            "id": txn_id,
            "description": row[1],
            "amount": row[2],
            "date": row[3],
            "type": row[4],
            "account_id": row[5],
            "status": "posted",
        }
        transactions.append(TellerTransaction(**txn_data))
        # Store account info and counterparty for later use
        account_info[txn_id] = {
            "name": row[6],
            "subtype": row[7],
            "counterparty": row[8],  # counterparty from JSON extraction
            "last_four": row[9],  # account last four digits
        }

    if not transactions:
        logger.info(
            "No uncategorized transactions found - all transactions already have categories!"
        )
        return

    # Check for manual categories that match current transactions
    manual_matches = 0
    if category_config.manual_categories:
        manual_map = {
            mc.transaction_id: mc.category for mc in category_config.manual_categories
        }
        manual_matches = sum(1 for txn in transactions if txn.id in manual_map)

    total_transactions = len(transactions)
    logger.debug(f"Converted to {total_transactions} TellerTransaction objects")
    total_batches = (total_transactions + batch_size - 1) // batch_size
    categorized_count = 0
    failed_count = 0

    categorization_methods = ["Claude AI"]
    if manual_matches > 0:
        categorization_methods.insert(0, f"manual rules ({manual_matches} matches)")

    logger.info(
        f"Categorizing {total_transactions} uncategorized transaction(s) using {' and '.join(categorization_methods)}"
    )
    logger.info(
        f"   Processing in {total_batches} batch(es) of up to {batch_size} transactions each"
    )

    if total_transactions > 100:
        logger.info("   Large transaction volume may hit Claude API rate limits")
        logger.info(
            "   Consider using '--from-date YYYY-MM-DD' flag to process recent transactions first"
        )

    # Process in batches
    for i in range(0, len(transactions), batch_size):
        batch = transactions[i : i + batch_size]
        batch_num = (i // batch_size) + 1

        logger.info(
            f"   Processing batch {batch_num}/{total_batches} ({len(batch)} transactions)..."
        )

        # Get account info for this batch
        batch_account_info = {t.id: account_info[t.id] for t in batch}

        # First, apply manual categorizations
        manual_results = manual_categorizer.categorize_batch(batch, batch_account_info)
        manual_txn_ids = {r.transaction_id for r in manual_results}

        # Find transactions that weren't manually categorized
        remaining_transactions = [txn for txn in batch if txn.id not in manual_txn_ids]

        # Apply Claude categorization to remaining transactions
        claude_results = []
        if remaining_transactions:
            claude_results = claude_categorizer.categorize_batch(
                remaining_transactions, batch_account_info
            )
        claude_txn_ids = {r.transaction_id for r in claude_results}

        # Update database with successful categorizations
        batch_success_count = 0
        batch_failed_count = 0

        # Update manual categorizations
        for result in manual_results:
            db.update_transaction_category(result.transaction_id, result.category, result.confidence)
            batch_success_count += 1

        # Update Claude categorizations
        for result in claude_results:
            db.update_transaction_category(result.transaction_id, result.category, result.confidence)
            batch_success_count += 1

        # Count transactions that failed categorization
        # These are transactions that weren't manually categorized and didn't get Claude results
        failed_txn_ids = set()
        for txn in batch:
            if txn.id not in manual_txn_ids and txn.id not in claude_txn_ids:
                failed_txn_ids.add(txn.id)
        batch_failed_count = len(failed_txn_ids)

        categorized_count += batch_success_count
        failed_count += batch_failed_count

        if batch_success_count == len(batch):
            logger.info(
                f"      Batch {batch_num} complete: {batch_success_count} categorized"
            )
        else:
            logger.warning(
                f"      Batch {batch_num} partial: {batch_success_count}/{len(batch)} categorized"
            )

    # Show final summary
    logger.info("Categorization complete")
    logger.info(f"   Successfully categorized: {categorized_count} transactions")
    if failed_count > 0:
        logger.warning(f"   Failed to categorize: {failed_count} transactions")
    logger.info(
        f"   Success rate: {(categorized_count / total_transactions * 100):.1f}%"
    )
