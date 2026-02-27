#!/bin/bash
set -e

REPO="lukearmistead/sprig"
INSTALL_DIR="$HOME/.local/bin"

OS=$(uname -s)
case "$OS" in
  Darwin) ;;
  *) echo "Unsupported OS: $OS (this script is macOS only)"; exit 1 ;;
esac

mkdir -p "$INSTALL_DIR"

echo "Downloading Sprig for $OS..."
curl -fsSL "https://github.com/$REPO/releases/latest/download/sprig-macos" -o "$INSTALL_DIR/sprig"
chmod +x "$INSTALL_DIR/sprig"

echo "Installed to $INSTALL_DIR/sprig"

case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *) echo "Add $INSTALL_DIR to your PATH: export PATH=\"$INSTALL_DIR:\$PATH\"" ;;
esac

echo "Run 'sprig sync' to get started."
