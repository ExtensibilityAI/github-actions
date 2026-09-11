#!/usr/bin/env bash
# Mirror .github/workflows/actionlint.yml composite metadata checks.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

while IFS= read -r -d '' action_file; do
  if ! grep -q '^runs:' "$action_file"; then
    echo "error: $action_file is missing a runs: section" >&2
    exit 1
  fi
  if ! grep -q 'using: composite' "$action_file"; then
    echo "error: $action_file must declare using: composite" >&2
    exit 1
  fi
done < <(find . -path './.git' -prune -o -name 'action.yml' -print0)

echo "composite action metadata OK"
