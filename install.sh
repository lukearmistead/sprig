#!/bin/bash
set -e

INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

echo "Downloading Sprig..."
curl -sL https://github.com/lukearmistead/sprig/releases/latest/download/sprig -o "$INSTALL_DIR/sprig"
chmod +x "$INSTALL_DIR/sprig"

echo "Installed to $INSTALL_DIR/sprig"
echo "Starting Sprig..."
"$INSTALL_DIR/sprig"
