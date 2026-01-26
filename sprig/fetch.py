"""Transaction fetching logic for Sprig."""

from datetime import date
from typing import Optional

import requests

from sprig.database import SprigDatabase
from sprig.logger import get_logger
from sprig.models import TellerAccount, TellerTransaction
from sprig.teller_client import TellerClient
import sprig.credentials as credentials

logger = get_logger("sprig.fetch")


class Fetcher:
    """Handles fetching accounts and transactions from Teller API."""

    def __init__(self, client: TellerClient, db: SprigDatabase, from_date: Optional[date] = None):
        self.client = client
        self.db = db
        self.from_date = from_date

    def fetch_all(self):
        """Fetch from Teller and store in DB."""
        access_tokens = credentials.get_access_tokens()
        for token_obj in access_tokens:
            self.fetch_token(token_obj.token)

    def fetch_token(self, token: str) -> bool:
        """Fetch accounts and transactions for a single token. Returns True on success."""
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
            self.fetch_account(token, account.id)

        return True

    def fetch_account(self, token: str, account_id: str):
        """Fetch transactions for a specific account."""
        transactions = self.client.get_transactions(token, account_id, start_date=self.from_date)

        for transaction_data in transactions:
            transaction = TellerTransaction(**transaction_data)
            if self.from_date and transaction.date < self.from_date:
                continue
            self.db.sync_transaction(transaction)
