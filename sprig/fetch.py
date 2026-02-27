"""Transaction fetching logic for Sprig."""

from datetime import date
from typing import Generator, List, Optional, Tuple

import requests

from sprig.logger import get_logger
from sprig.models import TellerAccount, TellerTransaction
from sprig.teller_client import TellerClient

logger = get_logger("sprig.fetch")


def _http_status(e: requests.HTTPError) -> int | None:
    return e.response.status_code if e.response is not None else None


def fetch_all(
    client: TellerClient,
    tokens: List[str],
    from_date: Optional[date] = None,
) -> Generator[Tuple[TellerAccount, List[TellerTransaction]], None, None]:
    """Yield (account, transactions) for every account across all tokens."""
    for token in tokens:
        yield from fetch_token(client, token, from_date)


def fetch_token(
    client: TellerClient,
    token: str,
    from_date: Optional[date] = None,
) -> Generator[Tuple[TellerAccount, List[TellerTransaction]], None, None]:
    """Yield (account, transactions) for each account under a token."""
    try:
        accounts = client.get_accounts(token)
    except requests.HTTPError as e:
        match _http_status(e):
            case 401:
                logger.warning(f"Token {token[:12]}... is expired — reconnect with `sprig connect`")
                return
            case 404:
                logger.warning(f"Token {token[:12]}... enrollment no longer exists — remove from config")
                return
            case _:
                raise

    for account_data in accounts:
        account = TellerAccount(**account_data)
        try:
            transactions = fetch_account(client, token, account.id, from_date)
        except requests.HTTPError as e:
            if _http_status(e) == 410:
                logger.warning(f"Account {account.id} is no longer available, skipping")
                continue
            raise
        yield account, transactions


def fetch_account(
    client: TellerClient,
    token: str,
    account_id: str,
    from_date: Optional[date] = None,
) -> List[TellerTransaction]:
    """Return transaction list for one account."""
    raw = client.get_transactions(token, account_id, start_date=from_date)
    return [TellerTransaction(**t) for t in raw]
