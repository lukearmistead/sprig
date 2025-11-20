"""Authentication server for Teller Connect integration."""

import os
import signal
import webbrowser
import threading
import time
from pathlib import Path
from typing import Optional

from flask import Flask, request, render_template, jsonify
from pydantic import ValidationError

from sprig.logger import get_logger
from sprig.models.runtime_config import TellerAccessToken
from sprig import credential_manager

logger = get_logger("sprig.auth")


def append_token_to_credentials(new_token: str) -> bool:
    """Add new access token to keyring."""
    return credential_manager.append_access_token(new_token)


def run_auth_server(app_id: str, environment: str = "development", port: int = 8001) -> Optional[str]:
    """Run Flask server to handle Teller Connect authentication."""

    accounts_added = 0
    shutdown_requested = False
    app = Flask(__name__, template_folder=Path(__file__).parent / "templates")

    @app.route("/")
    def index():
        """Serve the Teller Connect page."""
        return render_template("connect.html", app_id=app_id, environment=environment)

    @app.route("/save-token", methods=["POST"])
    def save_token():
        """Handle token from Teller Connect success callback."""
        nonlocal accounts_added

        data = request.get_json()
        token = data.get("accessToken")

        try:
            TellerAccessToken(token=token)
        except ValidationError:
            return jsonify({"success": False, "error": "Invalid token format"}), 400

        if append_token_to_credentials(token):
            accounts_added += 1
            return jsonify({
                "success": True,
                "message": f"Account saved successfully! Total accounts: {accounts_added}",
                "accounts_added": accounts_added
            })
        else:
            return jsonify({"success": False, "error": "Failed to save token"}), 500

    @app.route("/done", methods=["POST"])
    def done():
        """Handle user indicating they're done adding accounts."""
        nonlocal shutdown_requested
        shutdown_requested = True
        threading.Thread(target=lambda: (time.sleep(1), os.kill(os.getpid(), signal.SIGINT)), daemon=True).start()
        return jsonify({"success": True, "message": "Authentication complete!"})

    @app.route("/status")
    def status():
        """Health check endpoint."""
        return jsonify({"status": "running", "app_id": app_id, "environment": environment})

    url = f"http://localhost:{port}"
    logger.info(f"Opening browser to {url}")
    logger.info("Please complete the bank authentication in your browser...")

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        if not shutdown_requested:
            logger.warning("\nAuthentication cancelled.")

    if accounts_added > 0:
        logger.info(f"\nSuccessfully added {accounts_added} account(s)!")
        return str(accounts_added)
    return None


def prompt_for_credentials() -> bool:
    """Prompt user to set up credentials if not configured."""
    import getpass

    logger.info("First-time setup: Please enter your credentials")
    logger.info("=" * 50)

    app_id = input("Teller APP_ID (app_xxx): ").strip()
    if not app_id:
        logger.error("APP_ID is required")
        return False

    claude_key = getpass.getpass("Claude API Key (sk-ant-api03-xxx): ").strip()
    if not claude_key:
        logger.error("Claude API Key is required")
        return False

    cert_path = input("Certificate path (e.g., certs/certificate.pem): ").strip() or "certs/certificate.pem"
    key_path = input("Private key path (e.g., certs/private_key.pem): ").strip() or "certs/private_key.pem"

    # Store credentials
    if not credential_manager.set_credential(credential_manager.KEY_APP_ID, app_id):
        logger.error("Failed to store APP_ID")
        return False

    if not credential_manager.set_credential(credential_manager.KEY_CLAUDE_API_KEY, claude_key):
        logger.error("Failed to store Claude API Key")
        return False

    credential_manager.set_credential(credential_manager.KEY_CERT_PATH, cert_path)
    credential_manager.set_credential(credential_manager.KEY_KEY_PATH, key_path)
    credential_manager.set_credential(credential_manager.KEY_ENVIRONMENT, "development")
    credential_manager.set_credential(credential_manager.KEY_DATABASE_PATH, "sprig.db")

    logger.info("Credentials saved to keyring")
    return True


def authenticate(environment: str = "development", port: int = 8001) -> bool:
    """Authenticate with Teller. Prompts for credentials on first run."""

    app_id = credential_manager.get_credential(credential_manager.KEY_APP_ID)

    # First-time setup
    if not app_id:
        if not prompt_for_credentials():
            return False
        app_id = credential_manager.get_credential(credential_manager.KEY_APP_ID)

    logger.info(f"Starting Teller authentication (app: {app_id}, environment: {environment})")
    logger.debug(f"Authentication server will run on port {port}")
    result = run_auth_server(app_id, environment, port)

    if result:
        logger.debug(f"Authentication completed successfully with {result} account(s)")
        return True
    else:
        logger.error("Authentication failed or cancelled.")
        return False
