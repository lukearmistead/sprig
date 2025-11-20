"""Simple Teller API client."""

from pathlib import Path
import requests

from sprig.credentials import credentials


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
    
    def _make_request(self, access_token: str, endpoint: str):
        """Make authenticated request to Teller API."""
        url = f"{self.base_url}{endpoint}"
        auth = (access_token, "")
        headers = {"Content-Type": "application/json"}
        
        response = self.session.get(url, auth=auth, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def get_accounts(self, access_token: str):
        """Get all accounts for given access token."""
        return self._make_request(access_token, "/accounts")
    
    def get_transactions(self, access_token: str, account_id: str):
        """Get transactions for an account."""
        return self._make_request(access_token, f"/accounts/{account_id}/transactions")