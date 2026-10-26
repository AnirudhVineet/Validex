#!/usr/bin/env sh
# One-command clean demo start: wipe the database + stored files, regenerate SYNTHETIC documents, seed.
# Works offline once the Docker images have been built (no network needed at demo time).
#
#   ./scripts/reset-demo.sh           # Docker (Postgres)   - default
#   ./scripts/reset-demo.sh --build   # Docker, rebuilding images first (needs network the first time)
#   ./scripts/reset-demo.sh --local   # local dev (SQLite) using backend/.venv
set -e
cd "$(dirname "$0")/.."

if [ "$1" = "--local" ]; then
  if [ -x backend/.venv/Scripts/python ]; then PY=backend/.venv/Scripts/python; else PY=backend/.venv/bin/python; fi
  "$PY" seed/seed.py --reset
  echo "Local data reset. Start: (cd backend && $PY -m uvicorn app.main:app --port 8000) and (cd frontend && npm run dev)"
  exit 0
fi

docker compose down -v
if [ "$1" = "--build" ]; then docker compose up -d --build; else docker compose up -d; fi
echo "Waiting for the backend to seed..."
i=0
until curl -sf http://localhost:5173/api/health >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -gt 60 ] && { echo "Backend did not come up; see: docker compose logs backend"; exit 1; }
  sleep 3
done
# Copy the demo upload files generated inside the container, so their dates and certificate numbers match
# the MOCK issuer records the backend just generated (both are created relative to today's date).
rm -rf seed/output/demo_upload
mkdir -p seed/output
MSYS_NO_PATHCONV=1 docker compose cp backend:/app/seed/output/demo_upload seed/output/demo_upload >/dev/null
echo "Demo upload files: seed/output/demo_upload/"
echo "Ready: http://localhost:5173  (all demo accounts use password demo1234)"
