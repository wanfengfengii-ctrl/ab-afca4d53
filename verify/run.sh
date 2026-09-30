#!/usr/bin/env bash
# One-shot verification entrypoint.
#
# 1. waits until api and web report healthy,
# 2. runs backend pytest suite,
# 3. installs frontend deps and runs tests + production build,
# 4. runs the closure-network API smoke test,
# then exits with an aggregated code (bit 0: backend tests, bit 1: frontend,
# bit 2: smoke / health).  compose gating (service_healthy) normally makes
# the wait instant; the loop keeps this script self-contained.

set -u

API_BASE="${API_BASE:-http://api:8000}"
WEB_BASE="${WEB_BASE:-http://web:8080}"
RC=0

echo "==> waiting for API health at ${API_BASE}/health"
python3 - <<'PY'
import os, sys, time, urllib.request
deadline = time.time() + 90
targets = [os.environ["API_BASE"] + "/health", os.environ["WEB_BASE"] + "/"]
pending = set(targets)
while time.time() < deadline and pending:
    for url in list(pending):
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    print(f"healthy: {url}")
                    pending.discard(url)
        except Exception:
            pass
    if pending:
        time.sleep(2)
if pending:
    print("ERROR: services never became healthy: " + ", ".join(sorted(pending)))
    sys.exit(1)
PY
if [ $? -ne 0 ]; then exit 4; fi

echo
echo "==> [1/3] backend code tests"
python3 -m venv /tmp/venv
/tmp/venv/bin/pip install --quiet --upgrade pip
/tmp/venv/bin/pip install --quiet -r /src/backend/requirements-dev.txt
( cd /src/backend && /tmp/venv/bin/python -m pytest -q )
[ $? -eq 0 ] || RC=$((RC | 1))

echo
echo "==> [2/3] frontend tests + production build"
(
    cd /src/frontend
    npm config set cache /tmp/npm-cache
    if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
    npm test && npm run build
)
[ $? -eq 0 ] || RC=$((RC | 2))

echo
echo "==> [3/3] closure-network API smoke test"
API_BASE="$API_BASE" WEB_BASE="$WEB_BASE" python3 /opt/verify/smoke.py
[ $? -eq 0 ] || RC=$((RC | 4))

echo
if [ "$RC" -eq 0 ]; then
    echo "VERIFY OK: backend tests, frontend build and API smoke all passed."
else
    echo "VERIFY FAILED (exit code $RC): bit0 backend, bit1 frontend, bit2 smoke."
fi
exit "$RC"
