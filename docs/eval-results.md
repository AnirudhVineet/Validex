# Validex evaluation results

Generated 2026-10-26 by `python -m scripts.evaluate`. OCR (Tesseract) available: **yes**.

> **These results are optimistic.** The team generated the documents, the variants, the expected findings and the checks; the layouts are clean and consistent. Real institutional documents will score lower. Treat these numbers as a regression baseline, not as accuracy claims.

## 1. Extraction accuracy (field values vs generator truth)

Overall: **99.5% (429/431)** of fields exactly correct. Document type classification: 100.0% (82/82). Documents not read (scan without OCR): 0.

| Field | Exactly correct |
|---|---|
| address | 100.0% (59/59) |
| certificate_number | 100.0% (63/63) |
| expiry_date | 100.0% (26/26) |
| faculty_count | 100.0% (19/19) |
| faculty_ids | 100.0% (19/19) |
| institution_name | 100.0% (82/82) |
| issue_date | 98.8% (80/81) |
| issuing_authority | 98.4% (62/63) |
| land_area_acres | 100.0% (19/19) |

| Method | Exactly correct |
|---|---|
| ocr | 83.3% (10/12) |
| pdf_text | 100.0% (419/419) |

Examples of misses:

| File | Field | Expected | Got |
|---|---|---|---|
| demo_upload/fire_noc__scanned.pdf | issuing_authority | Divisional Fire Officer, SYNTHETIC Fire Services | None |
| demo_upload/fire_noc__scanned.pdf | issue_date | 2026-01-13 | 43- 01-2026 — |

## 2. Validation rules (non-anomaly, non-verification), per scenario x rule id

Precision **1.00**, recall **1.00** (TP 16, FP 0, FN 0).


## 3. Anomaly indicators (ANO-*, XAPP-*)

Scenario level: precision **1.00**, recall **1.00** (TP 5, FP 0, FN 0).

| Signal | Result |
|---|---|
| PDF metadata signals on clean PDFs (false positives) | 0.0% (0/68) |
| Incremental update detected on 'altered' PDFs | 100.0% (2/2) |
| ELA flags on clean JPEGs (false positives) | 0.0% (0/20) |
| ELA flags on JPEGs with a pasted text patch | 0.0% (0/20) |
| Near-duplicate: rescan of the same page detected | 100.0% (10/10) |
| Near-duplicate: different doc types wrongly matched | 0.0% (0/40) |

ELA is expected to be weak on text documents (see docs/model-cards.md); it is kept only as a low-severity preliminary indicator.


## 4. MOCK issuer verification status handling

Correct status: **100.0% (36/36)** of verification requests.

| Expected | Actual | Count |
|---|---|---|
| expired | expired | 2 |
| manual_review | manual_review | 1 |
| mismatch | mismatch | 2 |
| pending | pending | 1 |
| source_unavailable | source_unavailable | 1 |
| verified | verified | 29 |

## 5. Hard examples

### 5a. Degraded scans (OCR)

| Scan quality | Fields exactly correct |
|---|---|
| scanned x1 | 57.7% (15/26) |
| scanned x2 | 46.2% (12/26) |

OCR'd values below 0.85 confidence are flagged for officer confirmation (EXT-001).

### 5b. Institution name matching (threshold 88)

| Case | Value | Should flag | Flagged | OK |
|---|---|---|---|---|
| Abbreviated name (same institution) | SYNTHETIC Inst. of Tech., Demo Nagar | False | True | **no** |
| Lower case and punctuation (same) | synthetic institute of technology demo nagar | False | False | yes |
| Different institution, similar name | SYNTHETIC Institute of Technology, Demo Nagari | True | False | **no** |
| Different institution, one word changed | SYNTHETIC Institute of Pharmacy, Demo Nagar | True | True | yes |
| Completely different institution | SYNTHETIC Riverside College of Arts, Elsewhere Town | True | True | yes |

Fuzzy matching cannot tell a near-identical name of a *different* institution from a typo. That is why name mismatches are findings for an officer, never automatic decisions, and why MOCK issuer verification compares names too.

## 6. Time per application (upload, extraction, analysis, verification, validation)

Median **0.82 s**, mean 0.90 s, max 1.55 s over 18 applications (single process, SQLite, this machine). Scans with OCR are the slowest.

Slowest: scanned_fire_noc 1.55 s, open_deficiency_faculty_gap 1.03 s, altered_fire_noc 1.01 s.

## 7. What these numbers do not show

- No real documents were used; layouts, fonts and wording are ours.
- Every issuer source is MOCK; real issuer APIs will fail and disagree in other ways.
- Rules and checklists are ILLUSTRATIVE, not the official AICTE handbook.
- No user study: the time-saved counter is an assumption, not a measurement.

