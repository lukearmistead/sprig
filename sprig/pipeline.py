"""Sync pipeline for Sprig."""

from sprig.categorize import categorize_uncategorized_transactions
from sprig.database import SprigDatabase, get_db_path
from sprig.export import export_transactions_to_csv
from sprig.fetch import Fetcher
from sprig.logger import get_logger
from sprig.models.config import Config
from sprig.teller_client import TellerClient

logger = get_logger("sprig.pipeline")

sync_state = {"status": "idle", "message": ""}


def run_sync():
    """Run the full sync pipeline in a background thread."""
    try:
        sync_state["status"] = "running"
        sync_state["message"] = "Fetching transactions..."

        config = Config.load()
        db = SprigDatabase(get_db_path())

        fetcher = Fetcher(TellerClient(), db, from_date=config.from_date)
        fetcher.fetch_all()

        sync_state["message"] = "Categorizing transactions..."
        categorize_uncategorized_transactions(db, config.batch_size)

        sync_state["message"] = "Exporting..."
        export_transactions_to_csv(get_db_path())

        sync_state["status"] = "done"
        sync_state["message"] = "Sync complete!"
    except Exception as e:
        logger.exception("Sync failed")
        sync_state["status"] = "error"
        sync_state["message"] = f"Sync failed: {e}"
