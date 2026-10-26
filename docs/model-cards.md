# Validex model cards

Validex has no machine-learned model in the decision path. Every compliance decision (required
documents, expiry, dates, ID formats, comparisons, statuses, permissions) is deterministic code
driven by versioned YAML rules. The components below produce *signals*; the rule engine turns
them into findings, and authorised officials decide. Anomaly signals are only ever reported as
**preliminary indicators that require manual review**.

All measurements are on our own SYNTHETIC documents, so they are optimistic. Real documents
vary far more. Full numbers: `docs/eval-results.md` (regenerate with `python -m scripts.evaluate`;
run it inside Docker so OCR is included).

---

## 1. Text extraction (pdfplumber + Tesseract OCR)
- **Purpose:** read institution name, certificate number, issuing authority, dates, address and
  faculty IDs, with page + bbox + confidence for every value.
- **How:** PDF text layer first; if a PDF has fewer than 15 words it is treated as a scan and OCR'd
  at 200 dpi. Fields are found by matching printed labels ("Valid Until:") with rapidfuzz.
- **Measured (eval-results.md):** 99.5% of fields exact overall; 100% on digital PDFs (419 fields);
  83% on the seeded noisy scans. OCR words are grouped by Tesseract's own line ids, because a slightly rotated
  scan drifts ~5 pt across a line (position-based grouping cut values off; 50% before this change).
- **Hard set:** all five types scanned once: 58% of fields exact; scanned twice: 46%. Scans are the weakest
  area; low-confidence OCR values are flagged for officer confirmation.
- **Limits / failure modes:** relies on "Label: value" lines on one text line; multi-column layouts,
  tables other than the faculty list, handwriting, stamps over text and non-English text are not handled.
  OCR confusions (O/0, l/1) can corrupt IDs; OCR values below 0.85 confidence are flagged for confirmation.
  Without Tesseract, scans are marked `failed` and their checks are listed as "could not complete".

## 2. Document type classification
- **Purpose:** warn when a file is uploaded into the wrong checklist slot (COMP-003).
- **How:** keyword counts from `config/doc_types.yaml`, title lines weighted x3. Deterministic.
- **Limits:** keyword lists are tuned to our synthetic titles; unfamiliar layouts return "unknown"
  (no finding), never a guess.

### Name / address matching (rapidfuzz, CONS-001 / CONS-002)
- Normalised (case, punctuation, filler words) token-sort similarity >= 88 for names, token-set >= 80 for addresses.
- **Known errors (eval hard set):** flags an abbreviated name of the same institution ("Inst. of Tech."), and
  misses a near-identical name of a different institution ("Demo Nagari" vs "Demo Nagar"). Findings only;
  issuer verification compares names independently.

## 3. QR decoding (OpenCV)
- **Purpose:** read the MOCK issuer reference printed as a QR code; it feeds verification.
- **Measured:** decodes all digital synthetic QR codes and the noisy scan at 200 dpi.
- **Limits:** damaged, tiny or low-contrast codes fail silently; the gateway then falls back to the
  extracted certificate number, or to manual review.

## 4. Issuer verification gateway (MOCK)
- **Purpose:** compare submitted values with the issuer's record. Six statuses: verified, mismatch,
  expired, pending, source_unavailable, manual_review.
- **All sources are MOCK** (`seed/output/mock_issuer_data.json`). No government system is contacted.
- **Rules:** names fuzzy-matched (>= 90), numbers and dates exact. Unknown reference or no values
  -> manual_review. Timeout / outage / missing data -> source_unavailable. Never invents a result.

## 5. Near-duplicate pages (perceptual hash) - ANO-002
- **How:** page 1 rasterised, median-filtered, Otsu-binarised, cropped to content, pHash with 576 bits.
- **Measured (4 seeds x 5 types):** same document re-scanned = 52-88 bits apart; different document types
  >= 106 apart. Threshold 96. Eval: 10/10 rescans detected, 0/40 cross-type false matches. Different certificates on the *same template* can be 56 apart, so this
  check only compares slots within one application (different document types).
- **Limits:** margin is modest; heavy rotation or cropping of a rescan can exceed the threshold
  (missed duplicate). A hit means "pages look alike", never "this is a copy".

## 6. PDF structure / metadata - ANO-003, ANO-005
- **Signals:** incremental updates after the first save, producer/creator naming an editing tool
  (short list), creation date before the printed issue date, modification before creation.
- **Conservative by design:** normal Word / LibreOffice / scanner producers are not flagged.
  Clean synthetic PDFs raise no signal (tested).
- **Limits:** form filling and digital signing also add incremental updates; metadata is easy to
  strip or forge, so absence of a signal proves nothing.

## 7. Error level analysis (ELA) - ANO-006, JPEG uploads only
- **How:** re-save at quality 90, 16 px block error means, flag a block > 6x the content median.
- **Measured honestly:** no false positives on 30 clean synthetic JPEGs (5 types x 2 seeds x 3 qualities),
  **but it also did not detect our simulated edits** (pasted text patches at several compression
  histories). ELA is a weak signal on text documents. It is kept for completeness and should not be
  relied on. Never applied to digital PDFs.

## 8. Digital signatures - SIG-001
- Presence only (signature field or /ByteRange). Reported as "signature present, not validated".
  No signature or certificate-chain validation is implemented.

## 9. Cross-application matching (XAPP-001..003)
- Exact file hash, exact certificate number, and >= 3 shared faculty IDs across *different* institutions.
- Deterministic; no fuzzy matching across institutions. False-positive sources: shared campus land,
  faculty who moved, template-issued certificates. Reported as preliminary indicators only.

## 10. Optional AI fallback reader for poor scans (off by default)
- **Purpose:** suggest field values when OCR misses a field, is unsure (< 0.85), or is not installed.
- **Model:** Groq vision model `qwen/qwen3.8-27b` (preview), strict JSON schema, temperature 0; page 1 as an image.
- **Safeguards:** values are stored as `ai_vision` with confidence 0.60 and `needs_confirmation`; no rule and no
  issuer comparison uses them until an officer confirms or corrects them (audited). Digital PDFs never call it.
  Null means "not readable" and stays missing. Region highlighting only when OCR finds the same text.
- **Limits:** not evaluated against a live key in this repo (calls are stubbed in tests). Vision models can misread
  digits or invent plausible text - which is exactly why confirmation is required. Preview models may be retired.

## 11. Optional AI case summary (off by default)
- **Purpose:** a short readable digest of already-computed findings for the officer.
- **Model:** Groq `openai/gpt-oss-120b`, strict JSON schema output.
- **Grounding:** input is the stored findings only; every output point must cite finding ids; points citing
  unknown ids are dropped; empty / declined -> "insufficient evidence". Never stored as a finding and never
  influences validation, statuses or the priority score.
- **Limits:** can still paraphrase a finding imperfectly - officers read the cited findings, not the summary.
  Not evaluated on real data.

## 12. Review-priority score
- Weighted count of open findings (critical 25, high 12, medium 5, low 2), +8 per anomaly indicator,
  +6 per verification issue, +3 per document with incomplete checks, +1 per day waiting (max 10); capped at 100.
- A queue-ordering aid with its full breakdown shown. **Not a probability** and not a compliance judgement.
  Hidden from applicants.
