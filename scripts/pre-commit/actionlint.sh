#!/usr/bin/env bash
# Mirror .github/workflows/actionlint.yml — lint reusable workflows only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ACTIONLINT_VERSION='1.7.12'
EXPECTED_SHA256='8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8'
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/github-actions-pre-commit"
BIN="$CACHE_DIR/actionlint-${ACTIONLINT_VERSION}"

if [[ ! -x "$BIN" ]]; then
  mkdir -p "$CACHE_DIR"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  url="https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz"
  curl -fsSL -o "$tmp/actionlint.tar.gz" "$url"
  actual="$(sha256sum "$tmp/actionlint.tar.gz" | awk '{print $1}')"
  if [[ "$actual" != "$EXPECTED_SHA256" ]]; then
    echo "actionlint checksum mismatch (got $actual, expected $EXPECTED_SHA256)" >&2
    exit 1
  fi
  tar -xzf "$tmp/actionlint.tar.gz" -C "$tmp" actionlint
  mv "$tmp/actionlint" "$BIN"
  chmod +x "$BIN"
  trap - EXIT
  rm -rf "$tmp"
fi

mapfile -t workflow_files < <(find .github/workflows -type f \( -name '*.yml' -o -name '*.yaml' \) | sort)
exec "$BIN" "${workflow_files[@]}"
