# Validex: presentation content

AI-assisted pre-validation of AICTE Extension of Approval (EoA) applications.
Hackathon prototype: synthetic data, MOCK issuers, illustrative rules.

---

## 1. TECHNICAL APPROACH

**Core idea**
- Pre-validate, flag, verify and explain; officers make every decision
- Fixed, versioned rules decide compliance; AI only reads documents and points out what to look at
- Every finding shows evidence: document, page, highlighted region, found vs expected, rule, next step

**How a document flows**
1. **Upload**: file type checked by content, size limit, SHA-256 fingerprint
2. **Read**: text from digital PDFs; OCR for scans; values saved with page and position
3. **Analyse**: QR code, page fingerprints, PDF edit history, signature presence
4. **Verify**: compare with the issuer's record (MOCK issuers in the prototype)
5. **Check**: 27 rules in YAML (missing, expired, dates, formats, name/address match, fee status, ...)
6. **Review**: officer resolves / dismisses / escalates each finding with a reason
7. **Decide**: Mark scrutiny complete / Return for correction / Escalate
8. **Record**: every action written to a tamper-evident (hash-chained) audit log

**Technology stack**
- Backend: Python, FastAPI, SQLAlchemy, PostgreSQL (SQLite for development)
- Frontend: React, Vite, Tailwind CSS
- Document reading: pdfplumber (digital PDFs), Tesseract OCR (scans)
- Image and PDF analysis: OpenCV (QR codes), imagehash (near-duplicates), pikepdf (edit history, signatures)
- Matching: rapidfuzz (fuzzy name and address matching)
- Optional AI (Groq, off by default): vision model reads poor scans; text model summarises findings
- Deployment: Docker Compose, one-command reset, works offline

**Roles**
- Applicant, Scrutiny officer, Senior authority, Inspector, Admin
- Permissions enforced on the server, not just hidden in the UI

**Design principles**
- Decision support only: no approve/reject button
- Deterministic rules: the same input always gives the same result
- "Preliminary indicator" wording for anomalies; never shown to applicants
- Never invent results: if a check can't run, it says so
- Everything simulated is labelled MOCK or SYNTHETIC

---

## 2. FEASIBILITY AND VIABILITY

**Already built and working**
- Full end-to-end prototype: upload, read, check, verify, review, decide, audit
- 147 automated tests passing; one-command demo reset
- 18 ready-made scenarios covering every feature

**Technically feasible**
- Uses mature, open-source tools (Tesseract, OpenCV, PostgreSQL, FastAPI, React)
- Runs on a single machine with Docker; no special hardware or GPU needed
- About 1 second to process an application (median, synthetic set)
- Works offline; AI features are optional

**Low cost**
- Open-source stack: no licence fees
- Optional AI uses a pay-per-use API only when OCR struggles

**Easy to adopt and change**
- Rules and checklists are YAML files, editable by authorised staff without code changes
- Every rule change is versioned and audited; old results are kept
- Issuer connections use a plug-in interface, so real issuers can replace the MOCK ones

**Risks and how we handle them**
| Risk | Mitigation |
|---|---|
| Poor scans read wrongly | Low-confidence values flagged; officer can correct; optional AI reader needs confirmation |
| False alarms on genuine documents | Conservative checks, tested on clean documents (0 false flags on 68 clean PDFs) |
| Issuer systems offline | Status "source unavailable", case goes to manual review |
| Over-trusting automation | Officers decide everything; every action needs a reason |
| Data privacy | Role-based access, 5-minute file links, masked IDs in logs |

**Path to production**
- Pilot with real (consented) documents to re-tune reading and thresholds
- Connect real issuer systems (fire services, accreditation bodies, land registries)
- Validate rules against the official AICTE Approval Process Handbook
- Add database migrations, a job queue, and digital signature validation

---

## 3. IMPACT AND BENEFITS

**For scrutiny officers**
- Routine checks done instantly and the same way every time
- Queue ordered by priority, so the most problematic cases come first
- Evidence highlighted on the page, so there's no hunting through documents
- Deficiency letters drafted automatically
- More time for judgement, less time on copying and cross-checking

**For institutions (applicants)**
- Pre-check catches problems before submission
- Clear explanation of every issue and how to fix it
- Fewer back-and-forth rounds

**For AICTE (the organisation)**
- Consistent scrutiny across officers and regions
- Faster processing of EoA applications
- Tamper-evident audit trail of every decision and change
- Dashboards: case status, delays, most common deficiencies, upcoming expiries
- Cross-application checks spot documents reused across institutions

**Transparency and trust**
- Every finding is explainable: rule, evidence, found vs expected
- Humans stay accountable for decisions
- Applicants never see unproven suspicion flags

**Results on our synthetic test set** (optimistic: we generated the data)
- 99.5% of document fields read exactly
- Validation rules: precision 1.00, recall 1.00
- Issuer verification status correct in 36 of 36 cases
- 0 false anomaly flags on 68 clean PDFs
- Known weak spots: badly degraded scans (46-58% of fields read exactly), near-identical institution names

---

## 4. RESEARCH AND REFERENCES

**Domain**
- AICTE Approval Process Handbook (published yearly): source for checklists and norms; our rules are illustrative and must be aligned with it. https://www.aicte-india.org
- AICTE Extension of Approval process: document requirements per category

**Document reading**
- Tesseract OCR (open-source OCR engine): https://github.com/tesseract-ocr/tesseract
- pdfplumber (text and positions from PDFs): https://github.com/jsvine/pdfplumber
- pypdfium2 (PDF page rendering): https://github.com/pypdfium2-team/pypdfium2

**Verification and analysis**
- OpenCV QR code detection: https://docs.opencv.org
- Perceptual image hashing (imagehash): https://github.com/JohannesBuchner/imagehash
- PDF structure and incremental updates (pikepdf, based on qpdf): https://github.com/pikepdf/pikepdf
- PDF specification (ISO 32000), incremental updates and signature fields
- Error Level Analysis: N. Krawetz, "A Picture's Worth...", Hacker Factor Solutions, 2007 (we found it weak on text documents)

**Matching and rules**
- rapidfuzz (fuzzy string matching): https://github.com/rapidfuzz/RapidFuzz
- YAML rule configuration with Pydantic validation: https://docs.pydantic.dev

**Platform**
- FastAPI: https://fastapi.tiangolo.com
- React: https://react.dev · Vite: https://vite.dev · Tailwind CSS: https://tailwindcss.com
- PostgreSQL: https://www.postgresql.org · Docker: https://www.docker.com

**Optional AI**
- Groq API (vision and text models, structured JSON outputs): https://console.groq.com/docs

**Our own evidence**
- Evaluation report: `docs/eval-results.md`
- Model cards (limits of each component): `docs/model-cards.md`
