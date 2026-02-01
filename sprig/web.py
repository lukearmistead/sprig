"""Web dashboard for Sprig."""

import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, request, render_template, jsonify
from pydantic import ValidationError

from sprig.logger import get_logger
from sprig.models.teller import TellerAccessToken
from sprig.pipeline import run_sync, sync_state
import sprig.credentials as credentials

logger = get_logger("sprig.web")

PORT = 8001


def get_template_folder() -> Path:
    """Get template folder path, handling PyInstaller bundles."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "templates"
    return Path(__file__).parent / "templates"


def create_app() -> Flask:
    """Create Flask app with all routes."""
    app = Flask(__name__, template_folder=get_template_folder())

    @app.route("/")
    def dashboard():
        """Serve the main dashboard."""
        return render_dashboard()

    @app.route("/sync", methods=["POST"])
    def sync():
        """Save credentials and start background sync."""
        app_id = request.form.get("app_id", "").strip()
        claude_key = request.form.get("claude_key", "").strip()

        if app_id:
            try:
                credentials.set_app_id(app_id)
            except ValidationError as e:
                return render_dashboard(status=f"Invalid APP_ID: {e}")

        if claude_key:
            try:
                credentials.set_claude_api_key(claude_key)
            except ValidationError as e:
                return render_dashboard(status=f"Invalid Claude API key: {e}")

        stored_app_id = credentials.get_app_id()
        stored_claude_key = credentials.get_claude_api_key()
        tokens = credentials.get_access_tokens()

        if not stored_app_id:
            return render_dashboard(status="Error: APP_ID required")
        if not stored_claude_key:
            return render_dashboard(status="Error: Claude API key required")
        if not tokens:
            return render_dashboard(status="Error: Connect a bank first")

        if sync_state["status"] == "running":
            return render_dashboard()

        threading.Thread(target=run_sync, daemon=True).start()
        return render_dashboard()

    @app.route("/sync/status")
    def sync_status():
        """Return current sync status as JSON."""
        return jsonify(sync_state)

    @app.route("/auth/connect")
    def auth_connect():
        """Redirect to Teller Connect page."""
        app_id = credentials.get_app_id()
        if not app_id:
            return render_dashboard(status="Error: Set APP_ID first")
        env = credentials.get_environment()
        return render_template("connect.html", app_id=app_id.value, environment=env.value)

    @app.route("/save-token", methods=["POST"])
    def save_token():
        """Handle token from Teller Connect success callback."""
        data = request.get_json()
        token = data.get("accessToken")

        try:
            TellerAccessToken(token=token)
        except ValidationError:
            return jsonify({"success": False, "error": "Invalid token format"}), 400

        if credentials.append_token(token):
            tokens = credentials.get_access_tokens()
            return jsonify({
                "success": True,
                "message": f"Account saved! Total accounts: {len(tokens)}",
                "accounts_added": len(tokens),
            })
        return jsonify({"success": False, "error": "Failed to save token"}), 500

    @app.route("/done", methods=["POST"])
    def done():
        """Handle completion of bank connection - redirect to dashboard."""
        return jsonify({"success": True, "message": "Accounts connected!", "redirect": "/"})

    def render_dashboard(status: str = ""):
        """Helper to render dashboard with current state."""
        app_id = credentials.get_app_id()
        claude_key = credentials.get_claude_api_key()
        certs_dir = credentials.get_default_certs_dir()
        exports_dir = credentials.get_default_exports_dir()
        tokens = credentials.get_access_tokens()

        return render_template(
            "dashboard.html",
            app_id=app_id.value if app_id else "",
            claude_key_masked=credentials.mask(claude_key.value if claude_key else None, 12),
            certs_dir=str(certs_dir),
            exports_dir=str(exports_dir),
            has_bank=len(tokens) > 0,
            bank_count=len(tokens),
            status=status,
            sync_state=sync_state,
        )

    return app


def start_dashboard():
    """Start web dashboard and open browser."""
    app = create_app()
    url = f"http://localhost:{PORT}"
    logger.info(f"Starting Sprig dashboard at {url}")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="0.0.0.0", port=PORT, debug=False)
