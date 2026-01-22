"""Simple Teller API client."""

from datetime import date
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

import sprig.credentials as credentials


def _is_rate_limit_error(exception):
    """Check if exception is a 429 rate limit error."""
    if isinstance(exception, requests.HTTPError):
        return exception.response is not None and exception.response.status_code == 429
    return False


class TellerClient:
    """Basic Teller API client."""

    def __init__(self):
        self.base_url = "https://api.teller.io"
        self.session = requests.Session()
        self._setup_mtls_certificates()

    def _setup_mtls_certificates(self):
        """Configure mTLS client certificates for authentication."""
        cert_path = credentials.get_cert_path()
        key_path = credentials.get_key_path()

        if cert_path and key_path:
            # Paths are already validated and resolved in credentials.get_*_path()
            self.session.cert = (str(cert_path.value), str(key_path.value))
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception(_is_rate_limit_error),
        reraise=True,
    )
    def _make_request(self, access_token: str, endpoint: str, params: Optional[dict] = None):
        """Make authenticated request to Teller API."""
        url = f"{self.base_url}{endpoint}"
        auth = (access_token, "")
        headers = {"Content-Type": "application/json"}

        response = self.session.get(url, auth=auth, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_accounts(self, access_token: str):
        """Get all accounts for given access token."""
        return self._make_request(access_token, "/accounts")
    
    def get_transactions(self, access_token: str, account_id: str, start_date: Optional[date] = None):
        """Get transactions for an account."""
        params = {"from_date": start_date.isoformat()} if start_date else None
        return self._make_request(access_token, f"/accounts/{account_id}/transactions", params=params)