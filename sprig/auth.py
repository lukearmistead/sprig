"""Authentication server for Teller Connect integration."""

import os
import webbrowser
import threading
import time
from pathlib import Path
from typing import Optional

from flask import Flask, request, render_template, jsonify
from dotenv import set_key
from pydantic import ValidationError

from sprig.models.runtime_config import TellerAccessToken


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
    
    captured_token = None
    app = Flask(__name__, template_folder=Path(__file__).parent / "templates")
    
    @app.route("/")
    def index():
        """Serve the Teller Connect page."""
        return render_template("connect.html", app_id=app_id, environment=environment)
    
    @app.route("/save-token", methods=["POST"])
    def save_token():
        """Handle token from Teller Connect success callback."""
        nonlocal captured_token
        
        data = request.get_json()
        token = data.get("accessToken")
        
        try:
            TellerAccessToken(token=token)
        except ValidationError:
            return jsonify({"success": False, "error": "Invalid token format"}), 400
        
        if append_token_to_env(token):
            captured_token = token
            threading.Thread(target=lambda: (time.sleep(1), os._exit(0)), daemon=True).start()
            return jsonify({"success": True, "message": "Token saved successfully! You can close this window."})
        else:
            return jsonify({"success": False, "error": "Failed to save token"}), 500
    
    @app.route("/status")
    def status():
        """Health check endpoint."""
        return jsonify({"status": "running", "app_id": app_id, "environment": environment})
    
    url = f"http://localhost:{port}"
    print(f"Opening browser to {url}")
    print("Complete the bank authentication in your browser...")
    
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        print("\nAuthentication cancelled.")
    
    return captured_token


def authenticate(environment: str = "development", port: int = 8001) -> bool:
    """Main authentication function."""
    
    app_id = os.getenv("APP_ID")
    if not app_id:
        print("Error: APP_ID not found in .env file")
        return False
    
    print(f"Starting Teller authentication for app {app_id} in {environment} environment...")
    token = run_auth_server(app_id, environment, port)
    
    if token:
        print("✅ Authentication successful! Token saved to .env")
        return True
    else:
        print("❌ Authentication failed or cancelled.")
        return False