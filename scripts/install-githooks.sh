#!/usr/bin/env bash
set -euo pipefail

# Install repo-local git hooks (versioned in .githooks/)
#
# This prevents unwanted trailers such as:
#   Co-authored-by: Cursor <cursoragent@cursor.com>

if ! command -v git >/dev/null 2>&1; then
  echo "git not found" >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "Not inside a git repo. Run this from within the repo." >&2
  exit 1
fi

cd "${repo_root}"

chmod +x .githooks/commit-msg || true
git config core.hooksPath .githooks

echo "Installed git hooks: core.hooksPath=.githooks"

#!/usr/bin/env bash
set -euo pipefail

# Install repo-local git hooks (versioned in .githooks/)
#
# This prevents unwanted trailers such as:
#   Co-authored-by: Cursor <cursoragent@cursor.com>

if ! command -v git >/dev/null 2>&1; then
  echo "git not found" >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "Not inside a git repo. Run this from within the repo." >&2
  exit 1
fi

cd "${repo_root}"

chmod +x .githooks/commit-msg || true
git config core.hooksPath .githooks

echo "Installed git hooks: core.hooksPath=.githooks"

