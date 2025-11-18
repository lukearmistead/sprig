"""Authentication server for Teller Connect integration."""

import os
import signal
import webbrowser
import threading
import time
from pathlib import Path
from typing import Optional

from flask import Flask, request, render_template, jsonify
from dotenv import set_key
from pydantic import ValidationError

from sprig.logger import get_logger
from sprig.models.runtime_config import TellerAccessToken

logger = get_logger("sprig.auth")


def append_token_to_env(new_token: str) -> bool:
    """Add new access token to .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    
    if not env_path.exists():
        return False
    
    existing_tokens = os.getenv("ACCESS_TOKENS", "")
    current_tokens = [token.strip() for token in existing_tokens.split(",") if token.strip()]
    
    if new_token not in current_tokens:
        current_tokens.append(new_token)
    
    updated_token_string = ",".join(current_tokens)
    set_key(env_path, "ACCESS_TOKENS", updated_token_string)
    
    return True


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

        if append_token_to_env(token):
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
    logger.info(f"🌐 Opening browser to {url}")
    logger.info("Please complete the bank authentication in your browser...")

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        if not shutdown_requested:
            logger.warning("\nAuthentication cancelled.")

    if accounts_added > 0:
        logger.info(f"\n✅ Successfully added {accounts_added} account(s)!")
        return str(accounts_added)
    return None


def authenticate(environment: str = "development", port: int = 8001) -> bool:
    """Main authentication function that supports adding multiple accounts via browser UI."""

    app_id = os.getenv("APP_ID")
    if not app_id:
        logger.error("❌ Error: APP_ID not found in .env file")
        logger.error("Please add your Teller APP_ID to the .env file")
        return False

    logger.info(f"🔐 Starting Teller authentication (app: {app_id}, environment: {environment})")
    logger.debug(f"Authentication server will run on port {port}")
    result = run_auth_server(app_id, environment, port)

    if result:
        # result contains the number of accounts added
        logger.debug(f"Authentication completed successfully with {result} account(s)")
        return True
    else:
        logger.error("❌ Authentication failed or cancelled.")
        return False
