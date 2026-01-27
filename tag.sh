#!/bin/bash
# Auto-tag based on manifest version and push
# Usage: ./tag.sh

set -e

MANIFEST="custom_components/export_monitor/manifest.json"
VERSION=$(grep '"version"' "$MANIFEST" | head -1 | sed 's/.*"version": "\([^"]*\)".*/\1/')

echo "Current version: v$VERSION"

# Check if tag exists
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
    echo "Tag v$VERSION already exists, skipping..."
else
    echo "Creating tag v$VERSION..."
    git tag "$VERSION"
    git push origin "$VERSION"
    echo "✓ Tagged and pushed v$VERSION"
fi
