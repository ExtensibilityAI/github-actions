#!/usr/bin/env bash
# Block commits that truncate an existing tracked file down to zero bytes.
# Catches accidental full-file wipes (e.g. an editor/agent overwriting a
# file with empty content) before they land. Deliberate `git rm` deletions
# are unaffected since this only looks at files still present in the commit.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

failed=0
while IFS=$'\t' read -r -d '' added _deleted path; do
  # Binary files report "-" for added/deleted line counts; skip them.
  [ "$added" = "-" ] && continue

  old_size=$(git show "HEAD:$path" 2>/dev/null | wc -c)
  new_size=$(git show ":$path" | wc -c)
  old_lines=$(git show "HEAD:$path" 2>/dev/null | wc -l)

  if [ "$old_size" -gt 0 ] && [ "$new_size" -eq 0 ]; then
    echo "no-truncate: '$path' had $old_lines line(s) at HEAD but is staged as empty" >&2
    failed=1
  fi
done < <(git diff --cached --diff-filter=M --numstat -z)

if [ "$failed" -ne 0 ]; then
  cat >&2 <<'EOF'

Blocked: this commit would empty out one or more existing files.
If that's really what you want, either:
  - re-check the diff and re-stage deliberately, or
  - commit with `git commit --no-verify` to bypass this check once.
EOF
  exit 1
fi
exit 0
