#!/bin/sh
# Install pre-commit hook
# Usage: ./install-hooks.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -d "$REPO_ROOT/.git" ]; then
    echo "Error: Not a git repository"
    exit 1
fi

cp "$SCRIPT_DIR/pre-commit" "$REPO_ROOT/.git/hooks/pre-commit"
chmod +x "$REPO_ROOT/.git/hooks/pre-commit"

echo "Pre-commit hook installed successfully!"
echo "The hook will run ruff and mypy before each commit."
