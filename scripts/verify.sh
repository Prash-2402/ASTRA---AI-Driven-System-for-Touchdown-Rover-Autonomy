#!/usr/bin/env bash
# Local pipeline check: backend tests, frontend typecheck + build.
set -euo pipefail
cd "$(dirname "$0")/.."
pytest -p no:warnings -q
( cd frontend && npx tsc -b --noEmit && npx vite build >/dev/null && echo "frontend OK" )
