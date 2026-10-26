# Validex (SIH prototype)

AI-assisted application and document pre-validation for AICTE Extension of Approval (EoA) scrutiny.
It pre-validates, flags, verifies and explains. **Authorised officials make every final decision.**

> Hackathon prototype. **Not an official AICTE system** and not endorsed by any government body.
> All data is SYNTHETIC. Checklists and rules are ILLUSTRATIVE, not taken from the official handbook.

Project rules: [CLAUDE.md](CLAUDE.md). Shared contracts: [docs/CONTRACTS.md](docs/CONTRACTS.md).
API summary: [docs/api-contract.md](docs/api-contract.md).

## Ports
| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API + Swagger | http://localhost:8000/docs |


## Option A: Docker (Postgres)
```bash
docker compose up --build        # seeds automatically on start (idempotent)
docker compose down              # stop
docker compose down -v           # stop AND wipe the database (clean demo start)
```

## Option B: Local dev (SQLite, Windows / Git Bash)
Backend (needs Python 3.11+; on Windows use the `py` launcher):
```bash
cd backend
py -3.12 -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # macOS/Linux: .venv/bin/pip
cd ..
backend/.venv/Scripts/python seed/seed.py --reset # create tables + SYNTHETIC seed
cd backend
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```
Frontend (Node 20+), in a second terminal:
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to 127.0.0.1:8000
```
OCR (Phase 1) needs Tesseract. It is included in the Docker image; for local dev on Windows install it
separately and add it to PATH, or run OCR work through Docker.

## Demo accounts (SYNTHETIC, password `demo1234`)
| Role | Email |
|---|---|
| applicant | applicant@validex.demo |
| scrutiny_officer | officer@validex.demo |
| senior_authority | senior@validex.demo |
| inspector | inspector@validex.demo |
| admin | admin@validex.demo |

## Tests
```bash
cd backend
.venv/Scripts/python -m pytest -q
```

## Regenerate contracts after changing schemas or routes
```bash
cd backend
.venv/Scripts/python -m scripts.export_schemas   # writes docs/schemas/*.json and docs/api-contract.md
```

## What is real vs MOCK / SYNTHETIC (Phase 0)
| Part | Status |
|---|---|
| JWT login, 5 roles, backend role checks | Real |
| Hash-chained audit log + `GET /api/audit/verify` | Real (tamper-evident, not immutable) |
| Dashboards | Real API, counts only (no data yet) |
| Institutions, users | SYNTHETIC |
| Issuer verification, documents, rules | Not built yet (Phase 1-2) |

## Security notes (only what is implemented)
- Passwords hashed with bcrypt. JWT (HS256) with an 8 hour expiry; set `JWT_SECRET` for any shared deployment.
- Every protected route checks the role in the backend; the frontend route guard is UX only.
- Audit events are SHA-256 hash-chained. Editing or deleting a row is detected by `verify_chain()`.
  Removing only the newest rows is not detectable from the chain alone.
- Not implemented (do not claim): encryption at rest, digital signature validation, rate limiting.

## Prototype limitations
- Tables are created with `create_all` (no migrations). Reset with `seed.py --reset` or `docker compose down -v`.
- Background jobs (later) use FastAPI BackgroundTasks: fine for a demo, not production-grade.
