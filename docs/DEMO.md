# Validex demo script (about 4 minutes)

Reset first: `./scripts/reset-demo.sh` (or `.\scripts\reset-demo.ps1`). Open http://localhost:5173.
All accounts use password `demo1234`. Keep `seed/output/demo_upload/` open in a file window.
Everything on screen is SYNTHETIC; every issuer source is MOCK.

| Time | Step | What to show and say |
|---|---|---|
| 0:00 | **Problem** (no clicks) | "EoA scrutiny means officers checking dozens of certificates per institution by hand: missing pages, expired NOCs, names that don't match, documents that may have been edited. Validex pre-validates, flags, verifies and explains. Officers still make every decision." |
| 0:25 | **Applicant pre-check** - `applicant@validex.demo` | Start application -> upload `fire_noc__expired.pdf`, `affidavit__valid.pdf`, `land_document__valid.pdf` -> **Run pre-check**. Point at: missing Faculty List (critical), expired NOC with found vs expected. "The applicant fixes problems *before* submitting." Upload `faculty_list__valid.pdf` -> **Submit**. |
| 1:05 | **Findings with evidence** - `officer@validex.demo` | Queue is sorted by review priority (show breakdown, "not a probability"). Open the new case -> **Start scrutiny** -> on the expired NOC click **Show evidence and explanation**: the page image with the date highlighted, rule, found vs expected, next step. |
| 1:40 | **Source verification (MOCK)** | Scroll to **Submitted value vs source value**: the MOCK fire registry confirms the expiry (VER-002). Open the **Mockingnagar** case from the queue: printed expiry 2030 vs issuer 2028 -> mismatch. |
| 2:05 | **Preliminary anomaly indicator** | Same case: "Preliminary indicator: file was modified after creation" (incremental PDF update by an editing tool). "We never say forged. Indicators are for manual review and the applicant never sees them." Optional: **Trialwadi** case shows a land document and faculty IDs also submitted by another institution. |
| 2:35 | **Officer review + audit** | Back on the first case: **Resolve** each critical/high finding with a reason -> **Mark scrutiny complete** (try it first to show it is blocked while critical findings are open). Show the case audit trail. |
| 3:05 | **Rule edit as admin** - `admin@validex.demo` | **Rule editor** -> change `within_days: 90` to `30` -> Validate -> reason -> Save as new version -> **Re-run on open cases**. "Rules are versioned YAML; every run records the version; old results are kept." Then **Audit and users** -> **Verify chain**: "tamper-evident hash chain". |
| 3:35 | **Impact + limitations** | Senior overview: ageing, common findings, expiry forecast, time saved (point at the stated ASSUMPTION). Limits: synthetic data, MOCK issuers, illustrative rules, OCR weaker on poor scans, ELA weak on text documents (see `docs/eval-results.md`). |

Fallback if something breaks live: every step also exists pre-seeded (Mockingnagar = altered NOC, Specimen Kunj = pending issuer,
Trialwadi = cross-application, Stubwadi = returned for correction, Synthpur = escalated for the inspector view).

---

## Judge Q&A cheat sheet

**Does AI approve or reject applications?** No. Deterministic rules produce findings; officers resolve, dismiss or escalate each with a reason and make every decision. There is no approve/reject button.

**Where is the AI then?** OCR (Tesseract), fuzzy name/address matching, QR decoding, perceptual hashing, PDF structure analysis. An optional LLM summary exists, is off by default, must cite finding IDs, and never affects validation.

**How do you avoid false accusations?** Anomaly signals are "preliminary indicators that require manual review", conservative by design (normal Word/scanner PDFs raise nothing; 0/68 clean PDFs flagged), hidden from applicants, and each says it may have a legitimate explanation.

**What if the issuer's system is down?** Status `source_unavailable`, a "manual review" finding, and nothing assumed. Unknown references and missing values go to `manual_review`. All six statuses are tested.

**Is the verification real?** No - every issuer is a MOCK service generated with the synthetic documents, labelled MOCK everywhere. The gateway has a connector interface for real issuers.

**How accurate is it?** On our synthetic set: 99.5% of fields exact on digital PDFs and seeded scans, validation precision/recall 1.00. These numbers are optimistic (we made the data). Degraded scans drop to 46-58% field accuracy; the name matcher misses "Demo Nagari" vs "Demo Nagar" and flags abbreviations. All in `docs/eval-results.md`.

**Can the audit log be tampered with?** It is tamper-*evident*: each event hashes the previous one; editing or deleting a row breaks `verify_chain()`. It is not immutable, and removing only the newest rows is not detectable from the chain alone.

**Can an applicant see an officer's flags?** No. Visibility is enforced in the backend (`visible_to_applicant`), with tests. Applicants also never see verification details or the priority score.

**Who can change rules?** Admin and senior authority only (backend-enforced, tested). Every change is a new version with a reason in the audit log; officers can only read rules.

**Are the checklists official?** No. They are ILLUSTRATIVE and must be checked against the current AICTE Approval Process Handbook.

**Digital signatures?** We detect that a signature is present and say "signature present, not validated". We do not validate signatures.

**What about privacy?** Synthetic data only. Files are served through 5-minute signed links, identifiers are masked in audit payloads, and uploads are checked by content (magic bytes) and size.

**What would you do next?** Pilot with real (consented) documents to re-tune extraction and thresholds, real issuer connectors (e.g. fire department registries), measured time-saved, signature validation, and production job queue + migrations.
