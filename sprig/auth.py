"""Authentication server for Teller Connect integration."""

import os
import signal
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

from flask import Flask, request, render_template, jsonify
from pydantic import ValidationError

from sprig.logger import get_logger
from sprig.models.config import Config
from sprig.models.teller import TellerAccessToken

logger = get_logger("sprig.auth")


def run_auth_server(config: Config, port: int = 8001) -> Optional[str]:
    """Run Flask server to handle Teller Connect authentication."""

    accounts_added = 0
    shutdown_requested = False
    app = Flask(__name__, template_folder=Path(__file__).parent / "templates")

    @app.route("/")
    def index():
        return render_template("connect.html", app_id=config.app_id, environment=config.environment)

    @app.route("/save-token", methods=["POST"])
    def save_token():
        nonlocal accounts_added
        data = request.get_json()
        token = data.get("accessToken")

        try:
            TellerAccessToken(token=token)
        except ValidationError:
            return jsonify({"success": False, "error": "Invalid token format"}), 400

        if token not in config.access_tokens:
            config.access_tokens.append(token)
        config.save()
        accounts_added += 1
        return jsonify({
            "success": True,
            "message": f"Account saved! Total: {accounts_added}",
            "accounts_added": accounts_added,
        })

    @app.route("/done", methods=["POST"])
    def done():
        nonlocal shutdown_requested
        shutdown_requested = True
        threading.Thread(
            target=lambda: (time.sleep(1), os.kill(os.getpid(), signal.SIGINT)), daemon=True
        ).start()
        return jsonify({"success": True, "message": "Authentication complete!"})

    @app.route("/status")
    def status():
        return jsonify({"status": "running", "app_id": config.app_id})

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


def authenticate(config: Config, port: int = 8001) -> bool:
    """Run Teller OAuth flow. Returns True if successful."""
    logger.info(f"Starting Teller authentication (app: {config.app_id})")
    result = run_auth_server(config, port)
    if result:
        return True
    logger.error("Authentication failed or cancelled.")
    return False
