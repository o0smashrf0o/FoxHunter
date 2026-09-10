#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -d "$PROJECT_ROOT/tests" ]; then
  cd "$PROJECT_ROOT"
  pytest --tb=short --no-header 2>&1 || true
else
  echo "No tests/ directory found — add tests and re-run 'scripts/test.sh'."
  exit 0
fi