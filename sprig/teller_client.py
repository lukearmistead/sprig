"""Simple Teller API client."""

from datetime import date
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception


def _is_rate_limit_error(exception):
    if isinstance(exception, requests.HTTPError):
        return exception.response is not None and exception.response.status_code == 429
    return False


class TellerClient:
    def __init__(self, cert_path: str, key_path: str):
        self.base_url = "https://api.teller.io"
        self.session = requests.Session()
        self.session.cert = (cert_path, key_path)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception(_is_rate_limit_error),
        reraise=True,
    )
    def _make_request(self, access_token: str, endpoint: str, params: Optional[dict] = None):
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(
            url, auth=(access_token, ""), headers={"Content-Type": "application/json"}, params=params
        )
        response.raise_for_status()
        return response.json()

    def get_accounts(self, access_token: str):
        return self._make_request(access_token, "/accounts")

    def get_transactions(self, access_token: str, account_id: str, start_date: Optional[date] = None):
        params = {"from_date": start_date.isoformat()} if start_date else None
        return self._make_request(access_token, f"/accounts/{account_id}/transactions", params=params)
