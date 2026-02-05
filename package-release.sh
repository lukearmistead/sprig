#!/bin/bash
# Build and package Sprig for release

set -e

echo "Cleaning previous build..."
if [[ -e dist/Sprig-Release ]]; then
    rm -r dist/Sprig-Release
fi
if [[ -e dist/Sprig-macos.zip ]]; then
    rm dist/Sprig-macos.zip
fi

echo "Building executable..."
pyinstaller sprig.spec

echo "Creating release folder..."
mkdir -p dist/Sprig-Release
cp dist/sprig dist/Sprig-Release/
cp launchers/*.command dist/Sprig-Release/
cp launchers/README.txt dist/Sprig-Release/
chmod +x dist/Sprig-Release/*.command

echo "Creating zip archive..."
cd dist && zip -r Sprig-macos.zip Sprig-Release

echo ""
echo "Done! Release package: dist/Sprig-macos.zip"
