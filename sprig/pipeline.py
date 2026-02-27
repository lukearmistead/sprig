"""Pipeline orchestrator — fetch → categorize → export."""

from typing import List

from sprig.categorize import categorize_manually, categorize_in_batches
from sprig.database import SprigDatabase
from sprig.export import export_transactions_to_csv
from sprig.fetch import fetch_all
from sprig.logger import get_logger
from sprig.models import TransactionCategory, TransactionView
from sprig.models.config import Config
from sprig.paths import get_default_db_path, resolve_cert_path
from sprig.teller_client import TellerClient

logger = get_logger()


def save_categories(db: SprigDatabase, categories: List[TransactionCategory]):
    """Persist categorization results to the database."""
    for cat in categories:
        db.update_transaction_category(cat.transaction_id, cat.category, cat.confidence)


def run_pipeline(config: Config):
    """Fetch, categorize, and export transactions."""
    db_path = get_default_db_path()
    db = SprigDatabase(db_path)

    logger.info("Fetching transactions from Teller")
    if config.from_date:
        logger.info(f"Filtering transactions from {config.from_date}")
    client = TellerClient(resolve_cert_path(config.cert_path), resolve_cert_path(config.key_path))
    for account, transactions in fetch_all(client, config.access_tokens, config.from_date):
        db.save_account(account)
        db.sync_transactions(transactions)

    logger.info("Applying manual overrides")
    save_categories(db, categorize_manually(config))

    logger.info("Categorizing transactions")
    uncategorized = db.get_uncategorized_transactions()
    views = [TransactionView.from_db_row(row) for row in uncategorized]
    if views:
        save_categories(db, categorize_in_batches(views, config))

    logger.info("Exporting to CSV")
    export_transactions_to_csv(db)
