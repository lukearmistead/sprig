#!/bin/bash
set -e

REPO="lukearmistead/sprig"
INSTALL_DIR="/usr/local/bin"

OS=$(uname -s)
case "$OS" in
  Darwin) ;;
  *) echo "Unsupported OS: $OS (this script is macOS only)"; exit 1 ;;
esac

ARCH=$(uname -m)
case "$ARCH" in
  arm64)  ASSET="sprig-macos-arm64" ;;
  x86_64) ASSET="sprig-macos-x86_64" ;;
  *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

echo "Downloading Sprig for macOS ($ARCH)..."
sudo curl -fsSL "https://github.com/$REPO/releases/latest/download/$ASSET" -o "$INSTALL_DIR/sprig"
sudo chmod +x "$INSTALL_DIR/sprig"

echo "Installed to $INSTALL_DIR/sprig"

echo ""
echo "Setup will walk you through connecting your accounts."
read -r -p "Press Enter to start setup..." < /dev/tty
exec "$INSTALL_DIR/sprig" sync
