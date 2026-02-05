#!/bin/bash
# Build and package Sprig for release

set -e

echo "Building executable..."
pyinstaller sprig.spec

echo "Creating release folder..."
mkdir -p dist/Sprig
cp dist/sprig dist/Sprig/
cp launchers/*.command dist/Sprig/
cp launchers/README.txt dist/Sprig/
chmod +x dist/Sprig/*.command

echo "Creating zip archive..."
cd dist && zip -r Sprig-macos.zip Sprig

echo ""
echo "Done! Release package: dist/Sprig-macos.zip"
