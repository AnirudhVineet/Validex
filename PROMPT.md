# Validex: master prompt (paste into Claude Code at the repo root)

```
Read CLAUDE.md first, then docs/PLAN.md. We are a 5-person SIH team building "Validex",
an AI-assisted document validation prototype for AICTE EoA applications. We have about
10 days. CLAUDE.md is the source of truth; if it conflicts with the plan, follow CLAUDE.md
and tell me.

You will create everything yourself: contracts, checklists, rules, seed data, synthetic
documents, mock services, tests, docs. I am not providing starter files.

## How we work
- Work in the phases below, in order. At the end of each phase STOP, summarize (what works,
  what is stubbed or mocked, how to run it, what is next) and wait for my "go".
- Before writing any code, reply with a short plan: repo layout, shared contracts
  (docs/CONTRACTS.md), REST endpoints, DB schema, and any ambiguity or contradiction you
  found in CLAUDE.md or the plan. Ask me about decisions instead of guessing. Wait for approval.
- Keep code simple and readable (intermediate team). Commit after each step.
- Run tests before saying anything is done. At least one test per service module.
- No LLM calls in validation logic, ever.
- Checklists and rules you write are ILLUSTRATIVE (the AICTE Approval Process Handbook is
  not in the repo unless I add it to docs/). Mark them so in the YAML and the UI.

## Phase 0: Foundation (contracts first)
1. Plan + contracts as described above. Wait for my approval.
2. Backend skeleton: FastAPI + SQLAlchemy models for User, Institution, Application,
   ApplicationDocument, ExtractedField, ChecklistItem/Rule (config-backed), ValidationRun,
   Finding, VerificationRequest, ReviewAction, AuditEvent, InspectionRecord, Notification.
   SQLite for dev, Postgres-ready.
3. Auth: JWT login, 5 roles, backend role-check dependency, tests for forbidden access.
4. audit.log(actor, event_type, target, payload), hash-chained from day one, verify_chain(),
   and a test that detects a tampered row. Every important write goes through it.
5. Export Pydantic schemas to docs/schemas/*.json and docs/api-contract.md.
6. React + Vite + Tailwind skeleton: login, role-based redirect, empty dashboards on the real API.
7. docker-compose.yml + README with exact run commands. Keep seed -> login working.

## Phase 1: Core workflow (protect this)
1. Seed script: ~25 fictional institutions marked SYNTHETIC (mock institute record includes
   prior EoA, approved intake, faculty count, deficiency status, ter_payment_status),
   one user per role, and two application categories with illustrative YAML checklists.
2. Synthetic document generator (script in seed/): fire NOC, affidavit, accreditation
   certificate, land document, faculty list, plus variants: valid, expired, missing field,
   name mismatch, and a harder scanned/noisy one. Fictional identifiers only. Include QR codes
   encoding a mock reference on documents that support it. Write a manifest of expected
   findings per document for later evaluation.
3. Applications: create, draft, submit, resubmit with version history. Dynamic checklist
   endpoint driven by YAML (required / optional / conditional states).
4. Upload: magic-byte validation, size limit, SHA-256, access-controlled short-lived file links.
5. Extraction: pdfplumber for digital PDFs, Tesseract for scans. Classify document type,
   extract fields (institution name, certificate number, issuing authority, issue and expiry
   dates, address). ALWAYS store page + bbox + confidence + source. Officer can correct a field (audited).
6. Rule engine: YAML rules, validated on load, rule-set version recorded per ValidationRun.
   Checks: missing document, blank required field, expired / expiring soon, invalid dates,
   identifier format, cross-document name/address mismatch (rapidfuzz), conflicts with the
   institute record (including TER payment status). Every Finding has all contract fields.
7. Structured validation report endpoint + page, filtered by role (visible_to_applicant
   enforced in the backend, with tests).
8. Dashboards: applicant (checklist, progress, pre-check findings) and officer (queue, status,
   deficiencies). Officer actions: resolve / dismiss / escalate a finding with a required reason;
   "Mark scrutiny complete / Return for correction / Escalate" on the application.
9. Pre-check: applicant can run validation before submitting and sees which checks could not complete.
10. Acceptance test: automated end-to-end test of seed -> login -> upload -> validate ->
    report -> officer review -> audit verify.
STOP for review.

## Phase 2: Verification and review tools
1. Mock issuer gateway (clearly labelled MOCK) with a pluggable connector interface and all six
   statuses, including timeout / source_unavailable. QR decoding (pyzbar/OpenCV) feeds it.
   Never invent a result; unreachable => source_unavailable + manual_review. Log source,
   reference, timestamp, response, mismatches.
2. UI: "Submitted value vs Source value" comparison panel.
3. Anomaly indicators (all labelled "preliminary indicator"): exact duplicate (SHA-256),
   near-duplicate (imagehash on rasterized pages), conservative PDF metadata / incremental-update
   checks, ELA only for JPEG-like images, mismatched identifiers and irregular dates.
   Detect digital-signature presence only and report "signature present, not validated".
   anomaly findings are visible_to_applicant = false.
4. Evidence highlighting: show the original document with the bbox region highlighted when
   a finding is selected; explainability panel (what was checked, found, expected, rule, next step).
5. Review-priority score with a visible factor breakdown. Describe it as a review-priority aid,
   never a probability of fraud. Hidden from applicants.
6. Alerts (missing, expired, pending verification too long, anomaly, awaiting correction) shown
   in dashboards, with notification records.
7. Rule editor UI for admin / senior_authority only: validate before save, version bump,
   re-run validation while preserving old results. Tests for officer being forbidden.
STOP for review.

## Phase 3: Differentiators and polish (only what time allows, in this order)
1. Cross-application intelligence: duplicate documents, reused certificate/faculty IDs,
   shown only to officers with a "may have a legitimate explanation" note.
2. Expiry forecast widget (configurable window) on officer and senior dashboards.
3. Senior authority dashboard: counts by status, ageing, common deficiencies.
4. Minimal inspector view: flagged cases + notes/evidence upload. Minimal infrastructure
   advisory: evidence-present checks and extracted labels only; no area measurement or seat
   counting claims.
5. Auto-drafted deficiency letter for officer review (template-based, no LLM needed).
6. Optional: evidence-grounded LLM summary of findings (must cite finding ids, may say
   "insufficient evidence", disabled by default, never affects validation).
7. Time-saved counter with the assumption shown on screen.
8. Cut unless I say otherwise: regulatory knowledge assistant, Hindi toggle, advanced charts.
STOP for review.

## Phase 4: Evaluation, docs, demo hardening
1. Evaluation script over the synthetic manifest: extraction accuracy, validation
   precision/recall, anomaly precision/recall and false positives on clean docs, verification
   status handling, time per application. Write docs/eval-results.md and state that results are
   optimistic because the data is team-generated; include the hard examples.
2. docs/model-cards.md: purpose, limits, known failure modes for each AI component.
3. docs/DEMO.md: a 4-minute script (problem, pre-check, findings, preliminary anomaly, source
   verification, officer review + audit, rule edit as admin, impact + limitations), plus a
   judge Q&A cheat sheet.
4. One-command reset-and-seed so the demo can restart from clean state. Offline-capable.
5. README: architecture diagram (text/mermaid), run commands, what is real vs MOCK/SYNTHETIC,
   security notes that only claim what is implemented, and a "prototype, not an official
   AICTE system" disclaimer shown in the UI footer.
6. Final checklist: tests green, hash-chain verify passes, no secrets or real data committed.

## Always
- Never use "forged" or "fraud" in code, UI, logs or docs. Use "preliminary indicator".
- Never label anything Approve/Reject.
- If you need a decision (naming, library, schema shape, scope cut), ask me.
- If time is tight, tell me which Phase 3 / Phase 2 items to cut; never weaken Phase 1.
- After each phase, tell each teammate what to do next (frontend, OCR/extraction,
  validation/anomaly, mock issuer + synthetic data, QA/demo).

Start now with the plan (no code yet).
```
