#!/usr/bin/env bash
# Run from repository root before committing quarterly-summary changes.
set -euo pipefail
python -m py_compile scripts/build_editorial.py
python -m unittest discover -s tests -p 'test_verified_dashboard.py' -v
node --check tests/live_browser_e2e.cjs
if [[ "${1:-}" == "--browser" ]]; then
  npm ls playwright >/dev/null 2>&1 || npm install --no-save playwright
  python -m http.server 8765 --bind 127.0.0.1 >/tmp/fb-precommit-http.log 2>&1 &
  server_pid=$!
  trap 'kill "$server_pid" 2>/dev/null || true' EXIT
  BAROMETER_URL=http://127.0.0.1:8765/ node tests/live_browser_e2e.cjs
fi
