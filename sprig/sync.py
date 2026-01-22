"""Transaction synchronization logic for Sprig."""

from datetime import date
from typing import Optional

import requests

from sprig.categorizer import categorize_uncategorized_transactions
from sprig.database import SprigDatabase
from sprig.logger import get_logger
from sprig.models import TellerAccount, TellerTransaction
from sprig.models.category_config import CategoryConfig
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
        transactions = self.client.get_transactions(token, account_id, start_date=self.from_date)

        for transaction_data in transactions:
            transaction = TellerTransaction(**transaction_data)
            if self.from_date and transaction.date < self.from_date:
                continue
            self.db.sync_transaction(transaction)
