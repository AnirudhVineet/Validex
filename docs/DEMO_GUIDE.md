# Validex: complete demonstration guide

Everything the website can do, who can do it, how to do it, and what you should see.
For the short timed version for judges, see [DEMO.md](DEMO.md).

> Validex is a hackathon prototype, **not an official AICTE system**. All data is SYNTHETIC,
> every issuer source is MOCK, and checklists/rules are ILLUSTRATIVE.

---

## Contents
1. [What Validex is, in one minute](#1-what-validex-is-in-one-minute)
2. [Start, stop and reset](#2-start-stop-and-reset)
3. [Accounts](#3-accounts)
4. [Words you will see on screen](#4-words-you-will-see-on-screen)
5. [The files you upload during the demo](#5-the-files-you-upload-during-the-demo)
6. [Feature tour by role](#6-feature-tour-by-role)
   - [Applicant](#61-applicant-institution) · [Scrutiny officer](#62-scrutiny-officer) · [Senior authority](#63-senior-authority) · [Inspector](#64-inspector) · [Admin](#65-admin)
7. [Demo plans: 4, 10 and 20 minutes](#7-demo-plans)
8. [Every rule, what triggers it, who sees it](#8-every-rule-what-triggers-it-who-sees-it)
9. [Things to try ("what happens if...")](#9-things-to-try-what-happens-if)
10. [Troubleshooting](#10-troubleshooting)
11. [Limitations to say out loud](#11-limitations-to-say-out-loud)

---

## 1. What Validex is, in one minute

Institutions applying for **Extension of Approval (EoA)** upload certificates (fire safety NOC, affidavit,
land document, faculty list, accreditation). Officers normally check each one by hand.

Validex:
1. **Reads** each document (text from digital PDFs, OCR for scans) and records *where* on the page each value was found.
2. **Checks** it with fixed, versioned rules: missing documents, expired certificates, wrong dates, wrong number
   formats, names/addresses that do not match the institute record, unpaid fees.
3. **Verifies** certificates with the issuer (all issuers here are **MOCK** services).
4. **Flags** things worth a closer look as *preliminary indicators* (e.g. a PDF edited after it was issued).
5. **Explains** every finding: what was checked, what was found, what was expected, where on the page, what to do.
6. **Leaves every decision to a person.** Officers resolve/dismiss/escalate findings with a reason and choose
   *Mark scrutiny complete*, *Return for correction* or *Escalate*. There is no Approve/Reject button.
7. **Records everything** in a tamper-evident (hash-chained) audit log.

---

## 2. Start, stop and reset

| What | Command (run in the project folder) |
|---|---|
| Start (normal) | `docker compose up -d` then open **http://localhost:5173** |
| Clean demo start (wipe everything, reseed, refresh demo files) | `./scripts/reset-demo.sh` (PowerShell: `.\scripts\reset-demo.ps1`) |
| Rebuild after code changes | `./scripts/reset-demo.sh --build` |
| Stop | `docker compose down` |
| API documentation (Swagger) | http://localhost:8000/docs |

- Always run the **reset script before a demo**. It takes about 30 seconds, works offline once images exist,
  and copies fresh demo upload files to `seed/output/demo_upload/`. Those files must come from the same reset
  as the database, because all dates are generated relative to today.
- Use Docker for demos: scanned documents need the OCR engine (Tesseract), which is inside the Docker image.

---

## 3. Accounts

**Every account uses the password `demo1234`.** All accounts are SYNTHETIC.

### 3.1 Main demo accounts

| Role | Email | Lands on | Use it for |
|---|---|---|---|
| Applicant | `applicant@validex.demo` | My applications | Live upload + pre-check + submit. Institution: *SYNTHETIC Institute of Technology, Demo Nagar*. Starts with **no** application. |
| Scrutiny officer | `officer@validex.demo` | Queue | Reviewing cases, evidence, verification, decisions, letters |
| Senior authority | `senior@validex.demo` | Overview and cases | Dashboard, escalated cases, rule editor |
| Inspector | `inspector@validex.demo` | Flagged cases | Site-inspection notes and evidence (escalated cases only) |
| Admin | `admin@validex.demo` | Audit and users | Audit log + chain verification, users, rule editor |

### 3.2 Pre-seeded applications (one applicant account each)

Use these to show any feature instantly without uploading. Log in as the **officer** to review them,
or as the listed **applicant** to see the institution's (filtered) view.

| # | Applicant login | Institution (SYNTHETIC ...) | Status | What it demonstrates | Findings the officer sees |
|---|---|---|---|---|---|
| 1 | applicant1@validex.demo | Institute of Technology, Testpur | submitted | A clean application | none |
| 2 | applicant2@validex.demo | College of Pharmacy, Sampleville | under scrutiny | Expired fire NOC, confirmed by MOCK issuer | EXP-001, VER-002 |
| 3 | applicant3@validex.demo | Institute of Technology, Mockabad | submitted | Required affidavit missing | COMP-001 |
| 4 | applicant4@validex.demo | Inst. of Engg. and Technology, Fictiongarh | under scrutiny | Land document in another institution's name | CONS-001, VER-001 |
| 5 | applicant5@validex.demo | Institute of Technology, Placeholder Puram | submitted | TER fee unpaid on institute record | REC-001 |
| 6 | applicant6@validex.demo | College of Engineering, Example Kottai | submitted | Scanned fire NOC read by OCR | none in Docker (VER-003 if OCR is unavailable) |
| 7 | applicant7@validex.demo | School of Management, Dummy Ganj | submitted | Intake increase of 120 seats, so accreditation becomes required (conditional checklist) | COMP-001 |
| 8 | applicant8@validex.demo | Inst. of Engg. and Technology, Prototype Pet | under scrutiny | Accreditation expiring soon, faculty count 40% below record, open deficiency on record | EXP-002, CONS-003, REC-002 |
| 9 | applicant9@validex.demo | Inst. of Engg. and Technology, Synthpur | **escalated** | Certificate number in the wrong format; escalated, so the inspector can see it | FMT-001 |
| 10 | applicant10@validex.demo | Institute of Technology, Stubwadi | **returned for correction** | Officer returned it; applicant must fix and resubmit | EXP-001, VER-002 |
| 11 | applicant11@validex.demo | College of Engineering, Fixture Halli | **scrutiny complete** | Finished case | none |
| 12 | applicant12@validex.demo | Inst. of Engg. and Technology, Seedpur | **draft** | Applicant pre-check results before submitting (officers cannot see drafts) | COMP-002, REC-001 (pre-check) |
| 13 | applicant13@validex.demo | School of Management, **Mockingnagar** | under scrutiny | **Altered** fire NOC: printed expiry pushed out 2 years, PDF edited afterwards | VER-001, ANO-003 |
| 14 | applicant14@validex.demo | College of Engineering, Draftabad | submitted | Digitally signed PDF: "signature present, not validated" | SIG-001 (info) |
| 15 | applicant15@validex.demo | Inst. of Engg. and Technology, **Specimen Kunj** | under scrutiny | MOCK issuer still processing the land record; pending for 3 days, so an alert fires | VER-004 |
| 16 | applicant16@validex.demo | College of Engineering, Templategarh | submitted | MOCK fire registry times out, so "source unavailable" and manual review | VER-003 |
| 17 | applicant17@validex.demo | College of Pharmacy, Pilotpur | under scrutiny | The same affidavit file uploaded in the land document slot | ANO-001, COMP-002, COMP-003, VER-003 |
| 18 | applicant18@validex.demo | Inst. of Engg. and Technology, **Trialwadi** | under scrutiny | Land document and 5 faculty IDs also submitted by **another institution** (Testpur) | CONS-001, CONS-002, XAPP-001, XAPP-002, XAPP-003 |

25 institutions exist in total; the ones without applications only populate the institute records.

---

## 4. Words you will see on screen

**Application status:** `draft` -> `submitted` -> `under scrutiny` -> `scrutiny complete`, or
`returned for correction` (applicant fixes and resubmits as a new version), or `escalated` (senior authority decides).

**Finding:** one problem found by one rule. It always shows *Document, Found, Expected, Evidence (page + region +
text), Why, Suggested action, Rule id + version, Status*.

**Severity:** `critical` > `high` > `medium` > `low` > `info`. Critical/high findings must be handled before
*Mark scrutiny complete* is allowed.

**Finding status:** `open`, `resolved`, `dismissed`, `escalated`. Changing it always needs a written reason.

**Badges on findings:**
- `issuer check (MOCK)`: result of asking the (fake) issuing authority.
- `anomaly indicator`: a *preliminary indicator* that needs manual review. Never shown to applicants. Never means
  "forged".

**Verification status (MOCK issuer):** `verified`, `mismatch`, `expired`, `pending`, `source unavailable`,
`manual review`.

**Checks that could not complete:** a yellow box listing checks the system could *not* run (e.g. a scan without OCR).
Validex never guesses in that case.

**Review priority:** a number 0-100 used to order the officer queue. It is a weighted count of open issues with the
breakdown shown. **Not a probability**, not a compliance score.

**MOCK / SYNTHETIC / ILLUSTRATIVE:** fake issuer services / made-up data / example rules, not the official handbook.

---

## 5. The files you upload during the demo

Folder: `seed/output/demo_upload/` (all for *Demo Nagar*, the main applicant's institution).

| File | Upload into slot | What the applicant sees in pre-check | Extra things only the officer sees after submit |
|---|---|---|---|
| `fire_noc__valid.pdf` | Fire Safety NOC | nothing | issuer: verified |
| `fire_noc__expired.pdf` | Fire Safety NOC | **EXP-001** expired (critical) | **VER-002** issuer confirms expired |
| `fire_noc__scanned.pdf` | Fire Safety NOC | read with OCR (values may need confirmation) | issuer: verified via QR code; maybe EXT-001 (confirm OCR value) |
| `fire_noc__altered.pdf` | Fire Safety NOC | nothing (looks valid to the applicant) | **VER-001** issuer's expiry differs; **ANO-003** PDF modified after creation |
| `affidavit__valid.pdf` | Affidavit | nothing | - |
| `land_document__valid.pdf` | Land document | nothing | issuer: verified |
| `land_document__name_mismatch.pdf` | Land document | **CONS-001** name differs from record | **VER-001** issuer record names the real institution |
| `faculty_list__valid.pdf` | Faculty list | nothing | - |
| `accreditation_certificate__valid.pdf` | Accreditation (optional) | nothing | issuer: verified |
| `accreditation_certificate__signed.pdf` | Accreditation (optional) | nothing | **SIG-001** "signature present, not validated" |

Any PDF, PNG or JPEG up to 10 MB is accepted. Files are checked by their content, not their name, so a renamed
`.exe` is rejected.

---

## 6. Feature tour by role

The header shows your name, role and menu links. The footer on every page shows the prototype disclaimer.

### 6.1 Applicant (institution)

Login: `applicant@validex.demo`

| Feature | How | What happens |
|---|---|---|
| **Alerts** | Top of *My applications* | Missing/expired documents and "returned for correction" notices for your institution. *mark read* to clear. |
| **Start an application** | *Start a new application*: choose category and academic year, then **Start application** | Two categories (illustrative): *EoA: no change* and *EoA: increase in intake* (asks for **requested total intake**). Opens the workspace. |
| **Checklist** | Left card in the workspace | Each document shows **required / optional**. For *increase in intake*, accreditation becomes **required only if the increase is more than 60 seats**, and the reason is shown under the badge. |
| **Upload** | **Upload** button on a checklist row | File is checked (type, size), hashed (SHA-256), read, analysed. Status badge shows `extracted` (or `failed` with a reason). |
| **Replace a file** | **Replace** on the same row | Newer file becomes current; the old one is kept in history (audited). |
| **Extracted values** | *Uploaded documents and extracted values* | Every value read, with method (pdf_text / ocr), confidence, page. **View file** opens the original via a 5-minute link. |
| **Run pre-check** | **Run pre-check** (right card) | Runs all rules now, before submitting. Shows severity counts, findings, and checks that could not complete. Can be repeated after each upload. |
| **Show evidence and explanation** | Link on any finding | Original page image with the exact region highlighted + what was checked, rule, found vs expected, next step. |
| **Submit** | **Submit application** (bottom) | Allowed even with missing documents (shown as a warning). Submission snapshots version 1, runs MOCK issuer verification and the official validation. |
| **Resubmit** | After the officer returns it: replace files, then **Resubmit application** | Creates version 2 with a new snapshot; validation runs again. Notice at the top explains what to do. |
| **Printable report** | *Printable report* link | Clean report with checklist and findings, plus a *Print* button. |

What an applicant **never** sees: anomaly indicators, MOCK issuer comparisons, the review priority score,
cross-application matches, officer-only checks. This is enforced by the server, not just hidden in the page.

### 6.2 Scrutiny officer

Login: `officer@validex.demo`

**Queue page**
| Feature | What it shows / does |
|---|---|
| Status tiles | Counts of submitted, under scrutiny, escalated, returned, complete, and open findings (latest runs only) |
| **Alerts** | Preliminary anomaly indicators found; issuer verifications pending longer than 24 h |
| **Expiry forecast** | Documents expiring within 30 / 90 / 180 days (or already expired), with *open* links |
| **Time saved (estimate)** | Hours saved, with the **assumption printed in yellow** (6 min per document, 4 per issuer lookup, 10 per validation run; not measured) |
| Filters | all / submitted / under scrutiny / escalated / returned / complete |
| Queue table | Sorted by **review priority**; open and critical finding counts; **Review** opens the case |

**Case review page** (left column, top to bottom)
| Feature | How | What happens |
|---|---|---|
| **Start scrutiny** | Button on a `submitted` case | Moves it to `under scrutiny`; review buttons appear. |
| **Findings** | Main card | Run info (rule-set version, checklist version, application version), severity counts, incomplete checks, every finding with badges. |
| **Show evidence and explanation** | Link on a finding | Page image with the region highlighted + full explanation. For anomaly findings, a note that it is preliminary. |
| **Resolve / Dismiss / Escalate** a finding | Buttons under the finding, type a reason (min 5 characters), then **Confirm** | Status changes, reason saved, audit event written. Only *open* findings can be changed by an officer. |
| **Re-run validation** | Button on the findings card | New run with the current rules; earlier runs are kept; findings you already reviewed keep their status ("carried over"). |
| **Issuer verification: submitted value vs source value** | Card below findings | Per document: MOCK issuer, reference (from QR code or printed number), status, and a field table (submitted / source / matches or **differs**). **Re-verify (MOCK)** asks again and re-runs validation. |
| **Documents and extracted values** | Card at the bottom | Same as the applicant view plus **Correct** on every value: enter the new value + reason. Source becomes `manual`, the change is audited (IDs masked). Re-run validation afterwards. |
| **Confirm AI-read values** (only if the AI fallback is on) | Values marked **AI-read suggestion** have a **Confirm** button | The AI suggested them because OCR struggled. Rules ignore them until you confirm (or correct) against the document; then **Re-run validation**. |

**Case review page** (right column)
| Feature | What it does |
|---|---|
| **Decision** | **Mark scrutiny complete** (refused while open critical/high findings exist), **Return for correction** (applicant notified; next submission is a new version), **Escalate** (to the senior authority). Each needs a reason. |
| **Review priority (aid only)** | Score plus every factor and its points |
| **Deficiency letter (draft)** | **Draft deficiency letter** builds a template letter from findings the applicant may see (no AI). Edit it, **Copy**, or **Return for correction with this letter** (the letter becomes the reason the applicant sees). |
| **Case summary (optional AI)** | **Generate summary**. Off by default and says so. When enabled, every point cites finding ids; it never changes results. |
| **Inspection and infrastructure advisory** | Shows the inspector's notes and evidence, and which infrastructure items have evidence (read-only for officers) |
| **Institute record** | The MOCK record: reference, address, approved intake, faculty count, deficiency status, TER payment |
| **Checklist** | Uploaded / missing per document |
| **Audit trail** | Every event for this application, with reasons |

**Rules (read-only)** in the menu: the active rules file. Officers cannot edit it.

### 6.3 Senior authority

Login: `senior@validex.demo`

| Feature | How | What happens |
|---|---|---|
| **Overview** | Landing page | Applications by status; **ageing** bars (days since submission: 0-7, 8-14, 15-30, over 30); **most common open findings** bars (number of applications affected). Hover a bar for the exact value. |
| Queue, alerts, forecast, time saved | Same as officer | Default filter: **escalated** |
| **Decide escalated cases** | Open the escalated case (Synthpur) | **Mark scrutiny complete** or **Return for correction** (escalating further is not available). A senior can also change findings an officer escalated. |
| **Rule editor** | Menu: *Rule editor* | See 6.5 (same editor as admin). |

### 6.4 Inspector

Login: `inspector@validex.demo`

| Feature | How | What happens |
|---|---|---|
| **Flagged cases** | Landing page | Only **escalated** applications (seed: Synthpur). Other cases are blocked by the server. |
| **Infrastructure advisory** | Open a case | Five ILLUSTRATIVE items (classroom, laboratory, library, fire safety equipment, accessible entrance): *no evidence yet* or **evidence present (n)**, plus words read from the evidence. **No area measurement, seat counting or adequacy judgement.** |
| **Add an inspection record** | Type **Notes**, choose an **Evidence label**, choose a file (optional), **Save inspection record** | Saved and audited; evidence appears in the list (**View evidence file**) and the advisory updates. Officers see it on the case. Inspection files never enter validation. |
| Findings (read-only) | Right card | The case's findings, with evidence. |

### 6.5 Admin

Login: `admin@validex.demo`

| Feature | How | What happens |
|---|---|---|
| **Audit log** | Landing page | Latest 200 events: time, event type, target, actor, hash. |
| **Verify chain** | Button | Recomputes every hash: **"Chain intact: N events verified"** or the first broken event. Tamper-*evident*, not immutable. |
| **Users** | Same page | All users and roles. |
| **Rule editor** | Menu: *Rule editor* | YAML editor for the active rules. **Validate** (shows errors or "Valid: N rules") -> type a **reason** -> **Save as new version** (version number set automatically; old version kept). **Re-run on open cases** runs the new rules on every submitted / under scrutiny / escalated case; old runs and findings are kept for audit. |

---

## 7. Demo plans

Run `./scripts/reset-demo.sh` first. Have `seed/output/demo_upload/` open in a file window.

### 7.1 Four-minute version (for judges)
Follow [DEMO.md](DEMO.md): problem, then applicant pre-check, officer evidence, MOCK verification, preliminary
indicator, officer review + audit, rule edit, impact + limits.

### 7.2 Ten-minute version (step by step)

| Step | Login | Do this | You should see |
|---|---|---|---|
| 1 | applicant@ | **Start application** (EoA: no change, 2027-28) | Empty workspace, checklist with 4 required + 1 optional |
| 2 | applicant@ | Upload `fire_noc__expired.pdf`, `affidavit__valid.pdf`, `land_document__valid.pdf` | Three rows `extracted`; values listed below |
| 3 | applicant@ | **Run pre-check** | critical 2: *Required document missing: Faculty List* and *Fire NOC has expired* |
| 4 | applicant@ | On the expired finding: **Show evidence and explanation** | Page image with the expiry date boxed |
| 5 | applicant@ | Upload `faculty_list__valid.pdf`, then **Submit application** | Status `submitted` |
| 6 | officer@ | Queue: point out priority order, alerts, expiry forecast, time-saved assumption | New Demo Nagar case near the top |
| 7 | officer@ | **Review** -> **Start scrutiny** | Findings: EXP-001 (printed date) + VER-002 (issuer confirms) |
| 8 | officer@ | Scroll to **Issuer verification** | Fire NOC `expired`, land `verified`, field-by-field table |
| 9 | officer@ | **Mark scrutiny complete** with a reason | Refused: open critical/high findings must be handled first |
| 10 | officer@ | **Draft deficiency letter** -> **Return for correction with this letter** | Status `returned for correction` |
| 11 | applicant@ | Alert "returned for correction"; open the case; **Replace** fire NOC with `fire_noc__valid.pdf`; **Run pre-check**; **Resubmit** | Pre-check clean; version 2 submitted |
| 12 | officer@ | Open case -> **Start scrutiny** | No findings; **Mark scrutiny complete** with a reason works |
| 13 | officer@ | Open **Mockingnagar** | VER-001 (issuer expiry 2 years earlier) + ANO-003 preliminary indicator; evidence boxes the date |
| 14 | applicant13@ | Open the same application | Neither the issuer mismatch nor the indicator is visible |
| 15 | admin@ | **Verify chain** | "Chain intact" |

### 7.3 Twenty-minute full tour
Do 7.2, then:
1. **Conditional checklist**: as applicant@, start an *increase in intake* application with requested intake **420**
   (approved is 300, so +120): accreditation becomes **required**. Change it to **330** (+30): it becomes **optional**.
2. **Field correction**: as officer@ on any under-scrutiny case, **Correct** a value with a reason, then
   **Re-run validation**; show the audit trail entry.
3. **Issuer statuses**: Specimen Kunj (`pending`, plus the alert after 24 h), Templategarh (`source unavailable`,
   routed to manual review), Pilotpur (`manual review`, no reference).
4. **Cross-application**: Trialwadi: XAPP findings naming the other institution, each saying it may be legitimate.
5. **Signature**: Draftabad: "digital signature present, not validated".
6. **Escalation path**: officer escalates a case; inspector@ adds a note + evidence (label *laboratory*, any PDF);
   senior@ sees it and marks scrutiny complete.
7. **Rule change**: senior@ or admin@ edits `within_days: 90` to `30` on EXP-002, validates, saves with a reason,
   **Re-run on open cases**; Prototype Pet's EXP-002 disappears if the document expires in more than 30 days.
   Earlier runs stay in the audit.
8. **Senior overview**: ageing and common-findings bars.

---

## 8. Every rule, what triggers it, who sees it

All rules are ILLUSTRATIVE (`backend/config/rules/core.yaml`). "Applicant" = visible to the applicant.

| Rule | Checks | Severity | Applicant |
|---|---|---|---|
| COMP-001 | Every required checklist document is uploaded | critical | yes |
| COMP-002 | Key fields can be read (e.g. certificate number, dates) | high | yes |
| COMP-003 | The file matches its slot (keyword classification) | medium | yes |
| EXP-001 | Not expired on the scrutiny date | critical | yes |
| EXP-002 | Not expiring within 90 days | low | yes |
| DATE-001 | Issue date not in the future and before expiry | high | yes |
| FMT-001 | Certificate number format (e.g. `FNOC-YYYY-NNNNNN`) | medium | yes |
| CONS-001 | Institution name matches the institute record (fuzzy >= 88) | high | yes |
| CONS-002 | Address matches the record (fuzzy >= 80) | medium | yes |
| CONS-003 | Faculty list count within 10% of the record | medium | yes |
| REC-001 | TER payment is paid on the record | high | yes |
| REC-002 | No open deficiency on the record | medium | yes |
| EXT-001 | Low-confidence OCR value needs confirmation | info | no |
| VER-001 | MOCK issuer values match | high | no |
| VER-002 | MOCK issuer does not report it expired | high | no |
| VER-003 | Issuer reachable / reference found (else manual review) | medium | no |
| VER-004 | Issuer verification not pending | low | no |
| SIG-001 | Signature presence (not validated) | info | no |
| ANO-001 | Same file in two slots | medium | no |
| ANO-002 | Near-identical pages in two slots | low | no |
| ANO-003 | PDF modified after creation / editing-tool producer | medium | no |
| ANO-004 | QR reference differs from printed number | medium | no |
| ANO-005 | File dates inconsistent with printed issue date | low | no |
| ANO-006 | Uneven JPEG compression (ELA; weak signal) | low | no |
| XAPP-001 | Same file submitted by another institution | medium | no |
| XAPP-002 | Certificate number used by another institution | medium | no |
| XAPP-003 | 3+ faculty IDs also listed by another institution | low | no |

---

## 9. Things to try ("what happens if...")

| Try | Result |
|---|---|
| Upload a `.txt` renamed to `.pdf` | Rejected: "Unsupported file type" (checked by content) |
| Upload the affidavit into the land slot | COMP-003 "looks like a different document" (+ officer-only ANO-001 if the same file is in both slots) |
| Officer tries *Mark scrutiny complete* with open critical findings | Refused with the count of blocking findings |
| Reason shorter than 5 characters | Button stays disabled |
| Officer opens Rule editor URL directly | Read-only page; saving is refused by the server (403) |
| Inspector opens a non-escalated case | Not listed; server refuses access |
| Admin edits an audit row in the database | **Verify chain** reports the first broken event |
| Open a document link after 5 minutes | "Link expired or invalid" |

---

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| Page does not load | `docker compose ps`; if the backend is still seeding wait about 20 s; check `docker compose logs backend` |
| Port 8000 or 5173 busy | Stop the other program, or `docker compose down` and start again |
| Issuer shows *mismatch* on dates for a demo file you just uploaded | Demo files are from a different day than the database. Run `./scripts/reset-demo.sh` (it refreshes both). |
| Scanned file shows `failed` / checks that could not complete | OCR not available: you are running locally without Tesseract. Use Docker. |
| AI summary / AI reader says "disabled" or "unavailable" | Expected without a key. Add `GROQ_API_KEY`, `AI_FALLBACK_ENABLED=true`, `LLM_SUMMARY_ENABLED=true` to a `.env` file in the repo root, then `docker compose up -d`. |
| Something odd after many clicks | `./scripts/reset-demo.sh` returns to the clean seeded state |

---

## 11. Limitations to say out loud

- Prototype, not an official AICTE system; rules and checklists are ILLUSTRATIVE.
- All documents and institutions are SYNTHETIC; every issuer is MOCK.
- Accuracy numbers (`docs/eval-results.md`) are optimistic because we generated the data. Degraded scans drop to
  roughly 46-58% field accuracy; the name matcher can flag abbreviations and miss near-identical names.
- Anomaly indicators are preliminary; ELA did not catch our simulated JPEG edits.
- Digital signatures are detected, not validated.
- The time-saved number is an assumption, not a measurement.
- The audit log is tamper-evident, not immutable.
