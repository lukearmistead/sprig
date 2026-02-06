#!/bin/bash
cd "$(dirname "$0")"
echo "=== Sprig ==="
echo ""
./sprig sync
echo ""
read -p "Press Enter to close..."
