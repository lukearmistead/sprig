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

# Add to PATH if not already present
if ! echo ":$PATH:" | grep -q ":$INSTALL_DIR:"; then
  case "$SHELL" in
    */zsh)  RC_FILE="$HOME/.zshrc" ;;
    */bash) RC_FILE="$HOME/.bashrc" ;;
    *)      RC_FILE="$HOME/.profile" ;;
  esac

  EXPORT_LINE="export PATH=\"$INSTALL_DIR:\$PATH\""

  if ! grep -qF "$INSTALL_DIR" "$RC_FILE" 2>/dev/null; then
    echo "" >> "$RC_FILE"
    echo "$EXPORT_LINE" >> "$RC_FILE"
    echo "Added $INSTALL_DIR to PATH in $RC_FILE"
  fi

  echo "Restart your terminal or run: source $RC_FILE"
fi

echo ""
echo "Setup will walk you through connecting your accounts."
read -r -p "Press Enter to start setup..."
exec "$INSTALL_DIR/sprig" sync
