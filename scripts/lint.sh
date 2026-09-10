#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if command -v mypy >/dev/null 2>&1; then
  echo "Running mypy on utils/..."
  mypy --ignore-missing-imports utils/
  exit $?
fi

echo "mypy is not installed; running Python syntax checks instead."

failed=0

while IFS= read -r -d '' file; do
  if ! python3 -m py_compile "$file"; then
    failed=1
  fi
done < <(
  find "$PROJECT_ROOT" \
    -type f \
    -name '*.py' \
    -not -path '*/.venv/*' \
    -not -path '*/__pycache__/*' \
    -print0
)

if [[ "$failed" -ne 0 ]]; then
  echo "Python syntax checks failed." >&2
  exit 1
fi

echo "Python syntax checks passed."
