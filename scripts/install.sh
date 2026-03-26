#!/bin/bash
set -e

REPO="lukearmistead/sprig"
INSTALL_DIR="$HOME/.local/bin"

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
TMP=$(mktemp)
curl -fsSL "https://github.com/$REPO/releases/latest/download/$ASSET" -o "$TMP"

mkdir -p "$INSTALL_DIR"
install -m 755 "$TMP" "$INSTALL_DIR/sprig"
xattr -d com.apple.quarantine "$INSTALL_DIR/sprig" 2>/dev/null || true
rm -f "$TMP"

# Add to PATH if not already there
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$INSTALL_DIR"; then
  SHELL_NAME=$(basename "$SHELL")
  case "$SHELL_NAME" in
    zsh)  RC="$HOME/.zshrc" ;;
    bash) RC="$HOME/.bashrc" ;;
    *)    RC="$HOME/.profile" ;;
  esac
  echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$RC"
  export PATH="$INSTALL_DIR:$PATH"
  echo "Added $INSTALL_DIR to PATH in $RC"
fi

echo "Installed to $INSTALL_DIR/sprig"

echo ""
echo "Setup will walk you through connecting your accounts."
read -r -p "Press Enter to start setup..." < /dev/tty
"$INSTALL_DIR/sprig"
