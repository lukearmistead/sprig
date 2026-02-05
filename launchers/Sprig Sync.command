#!/bin/bash
cd "$(dirname "$0")"
echo "=== Sprig Sync ==="
echo ""
./sprig sync
echo ""
echo "--- Sync complete ---"
echo "Press any key to close..."
read -n 1
