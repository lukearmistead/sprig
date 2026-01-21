"""Transaction synchronization logic for Sprig."""

from datetime import date
from typing import Optional

import requests

from sprig.categorizer import categorize_in_batches
from sprig.database import SprigDatabase
from sprig.logger import get_logger
from sprig.models import TellerAccount, TellerTransaction
from sprig.models.category_config import CategoryConfig
from sprig.models.claude import TransactionView
from sprig.teller_client import TellerClient
import sprig.credentials as credentials

logger = get_logger("sprig.sync")


class Syncer:
    """Handles syncing accounts and transactions from Teller API."""

    def __init__(self, client: TellerClient, db: SprigDatabase, from_date: Optional[date] = None):
        self.client = client
        self.db = db
        self.from_date = from_date

    def sync_all(self, recategorize: bool = False, batch_size: Optional[int] = None):
        """Sync accounts and transactions for all access tokens."""
        access_tokens = credentials.get_access_tokens()

        if recategorize:
            self.db.clear_all_categories()

        for token_obj in access_tokens:
            self.sync_token(token_obj.token)

        category_config = CategoryConfig.load()
        effective_batch_size = batch_size if batch_size is not None else category_config.batch_size
        categorize_uncategorized_transactions(self.db, effective_batch_size)

    def sync_token(self, token: str) -> bool:
        """Sync accounts and transactions for a single token. Returns True on success."""
        try:
            accounts = self.client.get_accounts(token)
        except requests.HTTPError as e:
            if e.response and e.response.status_code == 401:
                logger.warning(f"Skipping invalid/expired token {token[:12]}...")
                return False
            raise

        for account_data in accounts:
            account = TellerAccount(**account_data)
            self.db.save_account(account)
            self.sync_account(token, account.id)

        return True

    def sync_account(self, token: str, account_id: str):
        """Sync transactions for a specific account."""
        transactions = self.client.get_transactions(token, account_id)

        for transaction_data in transactions:
            transaction = TellerTransaction(**transaction_data)
            if self.from_date and transaction.date < self.from_date:
                continue
            self.db.sync_transaction(transaction)


def apply_manual_overrides(db: SprigDatabase, category_config: CategoryConfig):
    """Apply manual category overrides from config."""
    if not category_config.manual_categories:
        return

    valid_category_names = {cat.name for cat in category_config.categories}

    for manual_cat in category_config.manual_categories:
        if manual_cat.category not in valid_category_names:
            logger.warning(f"Invalid category '{manual_cat.category}' for {manual_cat.transaction_id}")
            continue
        db.update_transaction_category(manual_cat.transaction_id, manual_cat.category, 1.0)


def categorize_uncategorized_transactions(db: SprigDatabase, batch_size: int):
    """Categorize transactions that don't have a category assigned."""
    category_config = CategoryConfig.load()
    apply_manual_overrides(db, category_config)

    uncategorized = db.get_uncategorized_transactions()
    transaction_views = [TransactionView.from_db_row(row) for row in uncategorized]

    if not transaction_views:
        return

    results = categorize_in_batches(transaction_views, category_config, batch_size)

    for result in results:
        db.update_transaction_category(result.transaction_id, result.category, result.confidence)
