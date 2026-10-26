# Validex: features at a glance

Website: http://localhost:5173 · All accounts use password **`demo1234`**
Everything is SYNTHETIC (fake data), every issuer is MOCK, rules are ILLUSTRATIVE.

---

## 1. Feature list

**Applicant (institution)**
- Start an application (2 categories: no change / increase in intake)
- Checklist shows required, optional, and conditional documents
- Upload PDF/PNG/JPEG (checked by content, size-limited, fingerprinted)
- Replace a file (old one kept in history)
- See values the system read from each document
- Run a pre-check before submitting
- See exactly where on the page each problem is, with an explanation
- Submit, and resubmit after correction (each submission is a new version)
- Alerts (missing/expired document, returned for correction)
- Printable report

**Automatic checks**
- Reads digital PDFs and scanned documents (OCR)
- Detects the document type, warns if it's in the wrong slot
- Missing required documents, blank key fields
- Expired / expiring-soon certificates
- Wrong dates (future issue date, issue after expiry)
- Certificate number format
- Name and address match the institute record
- Faculty count matches the record
- Fee (TER) paid, no open deficiency on record
- Checks that could not run are listed (never guessed)

**Certificate verification (MOCK issuers)**
- Reads the QR code on the certificate
- Compares document values with the issuer's record, side by side
- 6 results: verified, mismatch, expired, pending, source unavailable, manual review

**Warning flags (officers only, "preliminary indicators")**
- Same file uploaded twice
- Near-identical pages
- PDF edited after creation
- QR code doesn't match the printed number
- Odd file dates
- Digital signature present (detected, not validated)
- Same document, certificate number, or faculty IDs used by another institution

**Scrutiny officer**
- Queue sorted by review priority (with score breakdown)
- Alerts, expiry forecast, time-saved estimate
- Start scrutiny
- Resolve / dismiss / escalate each finding (reason required)
- Correct a wrongly-read value
- Re-verify with issuer, re-run checks
- Draft a deficiency letter and send it back
- Decide: mark scrutiny complete / return for correction / escalate (completion blocked while serious issues are open)
- Case audit trail
- Read rules (read-only)

**Senior authority**
- Overview: status counts, how long cases have waited, most common problems
- Decide escalated cases
- Rule editor: validate, save as new version, re-run checks

**Inspector**
- Sees escalated cases only
- Adds inspection notes and evidence files with a label
- Infrastructure checklist: evidence present or not

**Admin**
- Full audit log + tamper check ("Verify chain")
- User list
- Rule editor

**Optional AI (Groq, needs your key)**
- AI reader for poor scans: suggests values; officer must confirm before they're used
- AI case summary: summarises findings, must cite them

**Safety and trust**
- Humans make every decision (no approve/reject button)
- Applicants never see warning flags, issuer comparisons, or priority scores
- Each role can only do its own job (enforced on the server)
- Every important action is recorded in a tamper-evident audit log
- Documents open through 5-minute links only
- All data synthetic, issuers mock, rules illustrative

**Tools**
- One-command demo reset (`./scripts/reset-demo.sh`)
- Evaluation report with accuracy numbers (`docs/eval-results.md`)
- Demo script and full guide (`docs/DEMO.md`, `docs/DEMO_GUIDE.md`)

---

## 2. Why each feature exists (and what it does)

**Applicant side**
- **Categories + conditional checklist**: different applications need different documents; the checklist tells the applicant exactly what to upload.
- **Upload checks (content, size, fingerprint)**: blocks wrong or harmful files; the fingerprint proves the file was not changed later.
- **Replace with history**: lets applicants fix mistakes without losing the record of what was sent.
- **Extracted values**: shows the applicant what the system read, so errors are visible early.
- **Pre-check**: catches problems *before* submission, so fewer applications come back.
- **Evidence highlighting + explanation**: no "black box"; every problem points to the exact spot on the page and says why.
- **Versions on resubmit**: keeps a clear history of what changed between submissions.
- **Alerts**: the applicant knows what to fix without waiting to be told.
- **Printable report**: a record to keep or share.

**Automatic checks**
- **Text reading + OCR**: officers no longer copy values by hand from every certificate.
- **Document type detection**: catches a file uploaded into the wrong slot.
- **Missing / blank / expired / date / format checks**: the routine checks officers do on every file, done instantly and the same way every time.
- **Name, address, faculty, fee and deficiency checks**: confirms documents belong to *this* institution and match its record.
- **"Could not complete" list**: when something can't be checked, it says so instead of guessing.

**Certificate verification (MOCK)**
- **QR reading + issuer comparison**: confirms a certificate really exists with the issuer and its values match.
- **6 clear results**: officers see exactly what happened, including when the issuer could not be reached.

**Warning flags**
- **Duplicate / edited / mismatched / odd-date / shared-across-institutions flags**: point officers to documents that deserve a closer look.
- **"Preliminary indicator" wording, officers only**: a flag is a reason to look, not an accusation; applicants are never shown them.
- **Signature presence**: tells the officer a signature exists, without claiming it was validated.

**Officer tools**
- **Priority queue**: the cases with the most open issues are seen first; the breakdown shows why.
- **Expiry forecast**: spots certificates about to lapse.
- **Time-saved estimate**: shows impact (clearly marked as an assumption).
- **Resolve / dismiss / escalate with reason**: every human judgement is recorded and explainable.
- **Correct a value**: fixes reading mistakes; the correction is audited.
- **Re-verify / re-run**: re-check after new information arrives.
- **Deficiency letter**: saves writing time; uses only what the applicant is allowed to see.
- **Three decisions, never approve/reject**: the system supports officers, it does not replace them.
- **Completion block**: a case can't be closed while serious issues are still open.
- **Audit trail**: anyone reviewing the case can see who did what and why.

**Senior authority**
- **Overview**: see workload, delays, and the most common problems at a glance.
- **Escalated cases**: hard cases go to someone with more authority.
- **Rule editor with versions**: rules can change without code; every change is versioned, explained, and old results are kept.

**Inspector**
- **Flagged cases + notes + evidence**: adds on-site facts to cases that need them.
- **Infrastructure checklist**: shows only whether evidence exists; makes no claims about size or adequacy.

**Admin**
- **Audit log + tamper check**: proves the record has not been quietly edited.
- **Users + rule editor**: basic administration.

**Optional AI**
- **AI scan reader**: helps with poor scans; an officer must confirm every value, so AI never decides.
- **AI summary**: a quick overview for officers; must cite findings, so it can't invent facts.

**Safety and trust**
- **Human decisions, role limits, applicant filtering, audit log, short-lived links**: keeps the system fair, private, and accountable.

---

## 3. Accounts

All passwords: **`demo1234`**

### Main accounts
| Account | Role | What it does |
|---|---|---|
| `applicant@validex.demo` | Applicant (*SYNTHETIC Institute of Technology, Demo Nagar*) | Creates an application, uploads files, runs pre-check, submits, resubmits. Starts with no application. |
| `officer@validex.demo` | Scrutiny officer | Reviews cases, checks evidence and verification, resolves findings, drafts letters, makes decisions. |
| `senior@validex.demo` | Senior authority | Sees the overview, decides escalated cases, edits rules. |
| `inspector@validex.demo` | Inspector | Sees escalated cases, adds inspection notes and evidence. |
| `admin@validex.demo` | Admin | Views and verifies the audit log, sees users, edits rules. |

### Ready-made applicant accounts (one pre-seeded application each)
| Account | Institution (SYNTHETIC ...) | Status | Shows |
|---|---|---|---|
| applicant1@validex.demo | Institute of Technology, Testpur | submitted | A clean application |
| applicant2@validex.demo | College of Pharmacy, Sampleville | under scrutiny | Expired fire NOC |
| applicant3@validex.demo | Institute of Technology, Mockabad | submitted | Missing affidavit |
| applicant4@validex.demo | Inst. of Engg. & Tech., Fictiongarh | under scrutiny | Land document in another name |
| applicant5@validex.demo | Institute of Technology, Placeholder Puram | submitted | Fee (TER) unpaid |
| applicant6@validex.demo | College of Engineering, Example Kottai | submitted | Scanned document read by OCR |
| applicant7@validex.demo | School of Management, Dummy Ganj | submitted | Intake increase needs accreditation |
| applicant8@validex.demo | Inst. of Engg. & Tech., Prototype Pet | under scrutiny | Expiring soon, faculty gap, open deficiency |
| applicant9@validex.demo | Inst. of Engg. & Tech., Synthpur | escalated | Wrong certificate format (inspector can see it) |
| applicant10@validex.demo | Institute of Technology, Stubwadi | returned for correction | Needs fixing and resubmitting |
| applicant11@validex.demo | College of Engineering, Fixture Halli | scrutiny complete | A finished case |
| applicant12@validex.demo | Inst. of Engg. & Tech., Seedpur | draft | Pre-check results before submitting |
| applicant13@validex.demo | School of Management, Mockingnagar | under scrutiny | Altered fire NOC (issuer mismatch + edit flag) |
| applicant14@validex.demo | College of Engineering, Draftabad | submitted | Signed PDF ("present, not validated") |
| applicant15@validex.demo | Inst. of Engg. & Tech., Specimen Kunj | under scrutiny | Issuer verification pending |
| applicant16@validex.demo | College of Engineering, Templategarh | submitted | Issuer unreachable (manual review) |
| applicant17@validex.demo | College of Pharmacy, Pilotpur | under scrutiny | Same file uploaded in two slots |
| applicant18@validex.demo | Inst. of Engg. & Tech., Trialwadi | under scrutiny | Documents shared with another institution |

Tip: log in as `officer@validex.demo` to review any of these cases; log in as the applicant account to see what the institution sees (no warning flags).
