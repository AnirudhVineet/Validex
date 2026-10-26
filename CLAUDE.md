# CLAUDE.md: VerifyAI (SIH prototype)

## What this is
VerifyAI is an AI-assisted application and document validation prototype for AICTE
Extension of Approval (EoA) scrutiny. It pre-validates, flags, verifies and explains.
Authorized officials make every final decision. It is a hackathon prototype, NOT an
official AICTE system. Do not use official logos or imply government endorsement.

Team: 5 people, ~10 days, intermediate skill. Prefer simple, readable code over clever code.
Full plan: docs/PLAN.md. If this file and the plan conflict, this file wins; tell me about the conflict.
Shared contracts live in docs/CONTRACTS.md (you create and maintain it).

## Non-negotiable principles
1. Decision support only. The system never approves or rejects an institution.
   UI labels use "Mark scrutiny complete / Return for correction / Escalate", never "Approve/Reject".
2. Deterministic logic decides compliance: required docs, expiry, date checks, exact ID
   comparison, checklist rules, verification statuses, workflow state, permissions.
   NEVER use an LLM for these.
3. Anomaly results are "preliminary indicator" / "requires manual review". Never write
   "forged" or "fraud" in code, UI strings, logs or docs.
4. Every Finding carries evidence (document, page, bbox where available), the rule or
   comparison that triggered it, found value, expected value, explanation, suggested action.
5. Never invent verification results. Unreachable source => source_unavailable and route to manual_review.
6. Anything simulated is labelled "MOCK" or "SYNTHETIC" in code, API responses and UI.
   Never imply a mock is a live government integration.
7. Backend enforces permissions. Hiding a frontend button is not security.
8. Applicants must NOT see anomaly flags, review-priority scores or cross-application
   matches. Enforce via Finding.visible_to_applicant in the backend.
9. Synthetic data only. No real institutional documents, no real personal data.

## Tech stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy, Pydantic, SQLite (dev) / PostgreSQL (docker)
- Frontend: React + Vite + Tailwind (+ shadcn/ui)
- OCR/doc: pdfplumber (digital PDFs), Tesseract via pytesseract (scans); PaddleOCR optional only
- Image/PDF analysis: OpenCV, Pillow, pikepdf, imagehash, pyzbar
- Matching: rapidfuzz. Rules: YAML config + small Python evaluator
- Auth: JWT + role dependency. Jobs: FastAPI BackgroundTasks (prototype only, not production-grade)
- LLM (optional, Phase 3 only): evidence-grounded summaries. Never in the validation path.
- Run: docker compose up (exact commands in README)

## Repo layout
backend/app/        routes, models, schemas, services (ocr, rules, anomaly, verification, audit)
backend/config/     checklists/*.yaml, rules/*.yaml (versioned, illustrative, not official)
backend/tests/
frontend/src/
seed/               synthetic institutions, documents (clean + deliberately modified), mock issuer data
docs/               PLAN.md, CONTRACTS.md, api-contract.md, schemas/, model-cards.md, eval-results.md, DEMO.md

## Shared contracts (details go in docs/CONTRACTS.md; do not change without telling the team)
Enums:
- Roles: applicant, scrutiny_officer, senior_authority, inspector, admin
- ApplicationStatus: draft, submitted, under_scrutiny, returned_for_correction, escalated, scrutiny_complete
- DocumentStatus: uploaded, processing, extracted, failed
- VerificationStatus: verified, mismatch, expired, pending, source_unavailable, manual_review
- Severity: critical, high, medium, low, info
- FindingStatus: open, resolved, dismissed, escalated
- FindingCategory: completeness, expiry, consistency, anomaly, verification, infrastructure
- ExtractionSource: pdf_text, ocr, manual
Application status, verification status and anomaly status are SEPARATE fields.

Finding: id, application_id, document_id, validation_run_id, rule_id, rule_version, category,
severity, title, found_value, expected_value, evidence {page, bbox, snippet}, explanation,
suggested_action, status, visible_to_applicant, created_at, reviewed_by, review_reason.

ExtractedField: field_name, value, confidence, page, bbox, source, needs_confirmation.
ALWAYS store page + bbox from the first extraction so evidence highlighting is possible later.

VerificationResult: source, is_mock, reference_submitted, requested_at, status,
submitted_values, source_values, mismatches[], error.

AuditEvent: actor, event_type, target_type, target_id, payload, timestamp, prev_hash, hash.
All writes that matter go through audit.log(). The log is hash-chained (tamper-EVIDENT,
not "immutable"). Provide verify_chain() and keep its test passing.

## Rules engine
- Rules live in backend/config/rules/*.yaml: id, description, category, condition, severity,
  recommended_action, version, visible_to_applicant.
- Validate rule config before loading; reject malformed rules with a clear error.
- Every ValidationRun records the rule-set version used. Re-runs keep old results for audit.
- Checklist and rule content is ILLUSTRATIVE until checked against the current AICTE
  Approval Process Handbook. Never present it as official.
- Only admin / senior_authority can edit rules. Officers cannot.

## Conventions
- Type hints everywhere; small functions; docstrings on services.
- One router per resource. Business logic in services/, not in routes.
- Validate uploads by magic bytes, size limit and allowed types. Store SHA-256 of every file.
- Serve documents through access-controlled, short-lived links only.
- Mask IDs/personal fields in logs and non-privileged views.
- Don't claim encryption at rest, signature validation or measurement accuracy unless
  implemented and tested. Digital signatures: detect presence only ("signature present,
  not validated") unless a validator is actually built.
- Commit small and often. Branch per feature. Never commit secrets, .env or real data.

## Testing and definition of done
- At least one test per service module. Run the suite before saying work is complete.
- A feature is done when: it works end to end from the UI, has a test, writes the right
  audit events, and respects role permissions.
- Keep one demo path always working from a clean start:
  seed -> login -> upload -> validate -> report -> officer review -> audit view.

## Scope control (10-day plan)
- Phase 1 (Days 1-5, protect this): auth/roles, applications, 2 categories, upload,
  extraction for 4-5 doc types, deterministic missing/expiry/mismatch checks, report,
  basic dashboards, audit log.
- Phase 2 (Days 6-8): duplicate + metadata anomaly indicators, mock issuer service (6 statuses),
  submitted-vs-source view, evidence highlighting, alerts, review-priority score with
  breakdown, simple rule editor (admin only), officer resolve/escalate.
- Phase 3 (Days 9-10): cross-application duplicates, expiry forecast, minimal infrastructure
  advisory (evidence-present checks only), grounded summaries, time-saved counter
  (state its assumption on screen).
- Inspector role: minimal view only (flagged cases + notes/evidence upload form).
- CUT unless time remains: regulatory knowledge assistant, Hindi toggle, advanced charts.
- If time is tight, cut Phase 3, then Phase 2 items, before weakening Phase 1.

## Anomaly check notes
- Exact duplicates: SHA-256. Near-duplicates: imagehash on rasterized pages.
- ELA is only meaningful for JPEG-like images; rasterize PDFs first or skip ELA for digital PDFs.
- PDF metadata rules must be conservative (legit Word exports have normal creator/producer
  values). Prefer incremental-update/revision checks and creation-vs-modification gaps.
- Always test anomaly checks against clean documents to measure false positives.
- Metrics on our own synthetic set are optimistic: say so in eval docs, include some hard documents.

## Working with me
- Plan before coding on anything touching shared contracts, DB schema or auth.
- Ask when a decision is needed; don't guess silently.
- After each task, summarize: what works, what is stubbed or mocked, how to run it, what is next.
- Keep explanations short and point-based.
