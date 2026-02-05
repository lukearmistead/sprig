#!/bin/bash
cd "$(dirname "$0")"
echo "=== Sprig Connect ==="
echo ""
./sprig connect
echo ""
echo "Press any key to close..."
read -n 1
