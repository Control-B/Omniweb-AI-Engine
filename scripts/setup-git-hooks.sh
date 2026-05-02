#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" ]]; then
  echo "Not inside a git repository."
  exit 1
fi

source_hook="$repo_root/scripts/git-hooks/pre-push"
target_hook="$repo_root/.git/hooks/pre-push"

if [[ ! -f "$source_hook" ]]; then
  echo "Missing source hook at $source_hook"
  exit 1
fi

mkdir -p "$repo_root/.git/hooks"
cp "$source_hook" "$target_hook"
chmod +x "$target_hook"

echo "Installed pre-push hook: $target_hook"
