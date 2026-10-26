"""Evaluate Validex on freshly generated SYNTHETIC data and write docs/eval-results.md (+ .json).

Runs the real pipeline in an isolated temp database / storage folder (your demo data is not
touched): generate documents -> seed scenario applications through the services -> measure.

    python -m scripts.evaluate                    # from backend/, writes ../docs/eval-results.md
    python -m scripts.evaluate --out /tmp/eval.md # e.g. inside Docker (OCR available there)

Results are OPTIMISTIC: the team generated both the documents and the checks.
"""
import argparse
import os
import random
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="validex-eval-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TMP / 'eval.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(TMP / "files")
os.environ["MOCK_ISSUER_DATA_PATH"] = str(TMP / "docs" / "mock_issuer_data.json")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import json  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal, create_all  # noqa: E402
from app.enums import FindingCategory, Severity  # noqa: E402
from app.models import Finding, User  # noqa: E402
from app.services.analysis import analyze_file  # noqa: E402
from app.services.analysis.imaging import hash_distance  # noqa: E402
from app.services.extraction import ExtractionFailed, extract_file  # noqa: E402
from app.services.extraction.words import ocr_available  # noqa: E402
from app.services.rules import checks  # noqa: E402
from app.services.rules.context import DocView, FieldView, InstitutionView, ValidationContext  # noqa: E402
from app.services.validation import latest_run  # noqa: E402
from app.services.verification import latest_verifications  # noqa: E402
from seed import docgen  # noqa: E402
from seed import seed as seeding  # noqa: E402
from seed.generate_docs import generate_all  # noqa: E402

OUT_DOCS = TMP / "docs"
ANOMALY_PREFIXES = ("ANO-", "XAPP-")

# Expected MOCK verification status per (scenario, doc_type); everything else with an issuer -> verified.
EXPECTED_VERIFICATION = {
    ("expired_fire_noc", "fire_noc"): "expired",
    ("returned_expired", "fire_noc"): "expired",
    ("land_name_mismatch", "land_document"): "mismatch",
    ("altered_fire_noc", "fire_noc"): "mismatch",
    ("issuer_pending_land", "land_document"): "pending",
    ("issuer_timeout_fire", "fire_noc"): "source_unavailable",
    ("same_file_two_slots", "land_document"): "manual_review",
}


def pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{100 * n / d:.1f}% ({n}/{d})"


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r}


def fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


# ---------------------------------------------------------------- extraction

def evaluate_extraction(manifest: dict) -> dict:
    per_field: dict[str, list[int]] = {}
    per_method: dict[str, list[int]] = {}
    classified_ok = classified_total = failed = 0
    misses = []
    for entry in manifest["documents"]:
        path = OUT_DOCS / entry["file"]
        try:
            method, classified, parsed = extract_file(path, "application/pdf", entry["doc_type"])
        except ExtractionFailed:
            failed += 1
            continue
        classified_total += 1
        classified_ok += classified == entry["doc_type"]
        for name, truth in entry["truth"].items():
            got = parsed.get(name)
            ok = int(got is not None and str(got.value) == str(truth))
            per_field.setdefault(name, [0, 0])
            per_field[name][0] += ok
            per_field[name][1] += 1
            per_method.setdefault(method, [0, 0])
            per_method[method][0] += ok
            per_method[method][1] += 1
            if not ok and len(misses) < 12:
                misses.append({"file": entry["file"], "field": name, "expected": truth,
                               "got": None if got is None else got.value})
    total = [sum(v[0] for v in per_field.values()), sum(v[1] for v in per_field.values())]
    return {"per_field": per_field, "per_method": per_method, "overall": total, "failed_no_ocr": failed,
            "classification": [classified_ok, classified_total], "misses": misses}


# ---------------------------------------------------------------- validation, anomaly, verification, timing

def run_scenarios(manifest: dict) -> tuple[list[dict], list[float]]:
    create_all()
    seeding.seed_users_and_demo_institution()
    db = SessionLocal()
    results, timings = [], []
    try:
        institutions = [seeding._get_or_create_institution(db, d) for d in seeding.build_institutions()]
        by_ref = {i.aicte_ref: i for i in institutions}
        officer = db.execute(select(User).where(User.email == "officer@validex.demo")).scalar_one()
        pw = seeding.hash_password(seeding.DEMO_PASSWORD)
        for n, spec in enumerate(manifest["applications"], start=1):
            start = time.perf_counter()
            app = seeding.seed_one_application(db, n, spec, by_ref, officer, pw, OUT_DOCS)
            timings.append(time.perf_counter() - start)
            run = latest_run(db, app, include_precheck=True)
            findings = list(db.execute(select(Finding).where(Finding.validation_run_id == run.id)).scalars())
            types = {d.id: d.doc_type for d in seeding.app_svc.current_documents(db, app)}
            ver = {types.get(v.document_id): v.status.value for v in latest_verifications(db, app).values()}
            results.append({
                "scenario": spec["scenario"], "needs_ocr": spec.get("needs_ocr", False),
                "expected": set(spec["expected_rule_ids"]),
                "actual": {f.rule_id for f in findings if f.severity != Severity.info},
                "anomaly_actual": {f.rule_id for f in findings if f.category == FindingCategory.anomaly},
                "incomplete": len(run.incomplete_checks or []), "verification": ver,
                "seconds": timings[-1],
            })
    finally:
        db.close()
    return results, timings


def score(results: list[dict], anomaly: bool) -> dict:
    tp = fp = fn = 0
    rows = []
    for r in results:
        if r["needs_ocr"] and not ocr_available():
            continue
        keep = (lambda rid: rid.startswith(ANOMALY_PREFIXES)) if anomaly else (lambda rid: not rid.startswith(ANOMALY_PREFIXES) and not rid.startswith("VER-"))
        exp = {x for x in r["expected"] if keep(x)}
        act = {x for x in r["actual"] if keep(x)} if not anomaly else {x for x in r["anomaly_actual"]}
        tp += len(exp & act)
        fp += len(act - exp)
        fn += len(exp - act)
        if exp != act:
            rows.append({"scenario": r["scenario"], "missed": sorted(exp - act), "extra": sorted(act - exp)})
    return {**prf(tp, fp, fn), "diffs": rows}


def verification_table(results: list[dict]) -> dict:
    confusion: dict[tuple[str, str], int] = {}
    for r in results:
        if r["needs_ocr"] and not ocr_available():
            continue
        for doc_type, actual in r["verification"].items():
            expected = EXPECTED_VERIFICATION.get((r["scenario"], doc_type), "verified")
            confusion[(expected, actual)] = confusion.get((expected, actual), 0) + 1
    correct = sum(n for (e, a), n in confusion.items() if e == a)
    return {"confusion": confusion, "correct": correct, "total": sum(confusion.values())}


# ---------------------------------------------------------------- document-level anomaly signals

def anomaly_signals(manifest: dict) -> dict:
    clean = [e for e in manifest["documents"] if e["variant"] == "valid"]
    pdf_flags = 0
    for e in clean:
        pdf = analyze_file(OUT_DOCS / e["file"], "application/pdf").get("pdf", {})
        pdf_flags += bool(pdf.get("incremental_updates") or pdf.get("editing_tool") or pdf.get("signature_present"))
    altered = [e for e in manifest["documents"] if e["variant"] == "altered"]
    altered_hits = sum(bool(analyze_file(OUT_DOCS / e["file"], "application/pdf")["pdf"]["incremental_updates"])
                       for e in altered)

    # ELA: clean JPEG renders vs simulated local edits (expected to be weak).
    inst = docgen.InstitutionData("SYNTHETIC Eval Institute", "Eval Road, Testpur", "EVAL", "S", 10)
    ela_clean_fp = ela_edit_hits = ela_n = 0
    for t in docgen.DOC_TYPES:
        for seed in (1, 2):
            pdf = docgen.make_document(t, "valid", inst, date.today(), random.Random(seed)).pdf
            for q in (60, 85):
                jpeg = docgen.to_jpeg(pdf, q)
                edited = docgen.edit_jpeg(jpeg, (230, 500, 420, 530), "31-12-2031")
                for data, is_edit in ((jpeg, False), (edited, True)):
                    p = TMP / f"ela_{t}_{seed}_{q}_{is_edit}.jpg"
                    p.write_bytes(data)
                    flag = analyze_file(p, "image/jpeg")["ela"]["flag"]
                    if is_edit:
                        ela_edit_hits += flag
                    else:
                        ela_clean_fp += flag
                ela_n += 1

    # Near-duplicates: rescans of the same page (should match) vs different doc types (should not).
    rescan_hits = rescan_n = cross_fp = cross_n = 0
    hashes = {}
    for t in docgen.DOC_TYPES:
        for seed in (3, 4):
            g = docgen.make_document(t, "valid", inst, date.today(), random.Random(seed))
            a = TMP / f"nd_{t}_{seed}.pdf"
            b = TMP / f"nd_{t}_{seed}_scan.pdf"
            a.write_bytes(g.pdf)
            b.write_bytes(docgen.make_scanned(g.pdf, random.Random(seed + 7)))
            ha = analyze_file(a, "application/pdf")["page_hashes"][0]
            hb = analyze_file(b, "application/pdf")["page_hashes"][0]
            rescan_hits += hash_distance(ha, hb) <= 96
            rescan_n += 1
            hashes[(t, seed)] = ha
    keys = list(hashes)
    for i, k1 in enumerate(keys):
        for k2 in keys[i + 1:]:
            if k1[0] != k2[0]:
                cross_n += 1
                cross_fp += hash_distance(hashes[k1], hashes[k2]) <= 96
    return {"pdf_clean_fp": [pdf_flags, len(clean)], "altered_detected": [altered_hits, len(altered)],
            "ela_clean_fp": [ela_clean_fp, ela_n], "ela_edit_detected": [ela_edit_hits, ela_n],
            "near_dup_rescan_detected": [rescan_hits, rescan_n], "near_dup_cross_type_fp": [cross_fp, cross_n]}


# ---------------------------------------------------------------- hard examples

def hard_scans() -> dict:
    """Extraction on degraded scans (scanned twice: more blur, noise, rotation). Needs OCR."""
    if not ocr_available():
        return {"skipped": True}
    inst = docgen.InstitutionData("SYNTHETIC Institute of Technology, Demo Nagar",
                                  "Plot 12, Fictional Industrial Area, Demo Nagar, Sample State 000001", "H", "S", 12)
    per_level = {}
    for level in (1, 2):
        ok = n = 0
        for t in docgen.DOC_TYPES:
            g = docgen.make_document(t, "valid", inst, date.today(), random.Random(21))
            pdf = g.pdf
            for k in range(level):
                pdf = docgen.make_scanned(pdf, random.Random(30 + k))
            path = TMP / f"hard_{t}_{level}.pdf"
            path.write_bytes(pdf)
            try:
                _, _, parsed = extract_file(path, "application/pdf", t)
            except ExtractionFailed:
                parsed = {}
            for name, truth in g.truth.items():
                n += 1
                ok += int(name in parsed and str(parsed[name].value) == str(truth))
        per_level[f"scanned x{level}"] = [ok, n]
    return {"skipped": False, "per_level": per_level}


def hard_examples() -> list[dict]:
    """Cases chosen to show limits of the name matcher (threshold 88)."""
    record = "SYNTHETIC Institute of Technology, Demo Nagar"
    cases = [
        ("Abbreviated name (same institution)", "SYNTHETIC Inst. of Tech., Demo Nagar", False),
        ("Lower case and punctuation (same)", "synthetic institute of technology demo nagar", False),
        ("Different institution, similar name", "SYNTHETIC Institute of Technology, Demo Nagari", True),
        ("Different institution, one word changed", "SYNTHETIC Institute of Pharmacy, Demo Nagar", True),
        ("Completely different institution", "SYNTHETIC Riverside College of Arts, Elsewhere Town", True),
    ]
    inst = InstitutionView(record, "x", 1, 1, "none", "paid")
    out = []
    for label, name, should_flag in cases:
        doc = DocView("d", "fire_noc", "extracted", "fire_noc", None,
                      {"institution_name": FieldView("institution_name", name, 0.98, 1, None, "pdf_text", False)})
        ctx = ValidationContext(institution=inst, documents={"fire_noc": doc}, checklist=[], today=date.today())
        flagged = bool(checks.name_matches_record(ctx, checks.ThresholdParams(threshold=88)).findings)
        out.append({"case": label, "value": name, "should_flag": should_flag, "flagged": flagged,
                    "correct": flagged == should_flag})
    return out


# ---------------------------------------------------------------- report

def render(ext, val, ano, ver, signals, hard, timings, results, scans) -> str:
    L = []
    L.append("# Validex evaluation results\n")
    L.append(f"Generated {date.today().isoformat()} by `python -m scripts.evaluate`. "
             f"OCR (Tesseract) available: **{'yes' if ocr_available() else 'no'}**.\n")
    L.append("> **These results are optimistic.** The team generated the documents, the variants, the expected "
             "findings and the checks; the layouts are clean and consistent. Real institutional documents will "
             "score lower. Treat these numbers as a regression baseline, not as accuracy claims.\n")

    L.append("## 1. Extraction accuracy (field values vs generator truth)\n")
    L.append(f"Overall: **{pct(*ext['overall'])}** of fields exactly correct. "
             f"Document type classification: {pct(*ext['classification'])}. "
             f"Documents not read (scan without OCR): {ext['failed_no_ocr']}.\n")
    L.append("| Field | Exactly correct |\n|---|---|")
    for name, (ok, n) in sorted(ext["per_field"].items()):
        L.append(f"| {name} | {pct(ok, n)} |")
    L.append("\n| Method | Exactly correct |\n|---|---|")
    for m, (ok, n) in sorted(ext["per_method"].items()):
        L.append(f"| {m} | {pct(ok, n)} |")
    if ext["misses"]:
        L.append("\nExamples of misses:\n")
        L.append("| File | Field | Expected | Got |\n|---|---|---|---|")
        for m in ext["misses"]:
            L.append(f"| {m['file']} | {m['field']} | {m['expected']} | {m['got']} |")

    L.append("\n## 2. Validation rules (non-anomaly, non-verification), per scenario x rule id\n")
    L.append(f"Precision **{fmt(val['precision'])}**, recall **{fmt(val['recall'])}** "
             f"(TP {val['tp']}, FP {val['fp']}, FN {val['fn']}).\n")
    L.append("\n## 3. Anomaly indicators (ANO-*, XAPP-*)\n")
    L.append(f"Scenario level: precision **{fmt(ano['precision'])}**, recall **{fmt(ano['recall'])}** "
             f"(TP {ano['tp']}, FP {ano['fp']}, FN {ano['fn']}).\n")
    s = signals
    L.append("| Signal | Result |\n|---|---|")
    L.append(f"| PDF metadata signals on clean PDFs (false positives) | {pct(*s['pdf_clean_fp'])} |")
    L.append(f"| Incremental update detected on 'altered' PDFs | {pct(*s['altered_detected'])} |")
    L.append(f"| ELA flags on clean JPEGs (false positives) | {pct(*s['ela_clean_fp'])} |")
    L.append(f"| ELA flags on JPEGs with a pasted text patch | {pct(*s['ela_edit_detected'])} |")
    L.append(f"| Near-duplicate: rescan of the same page detected | {pct(*s['near_dup_rescan_detected'])} |")
    L.append(f"| Near-duplicate: different doc types wrongly matched | {pct(*s['near_dup_cross_type_fp'])} |")
    L.append("\nELA is expected to be weak on text documents (see docs/model-cards.md); it is kept only as a "
             "low-severity preliminary indicator.\n")
    for title, block in (("Validation", val), ("Anomaly", ano)):
        if block["diffs"]:
            L.append(f"\n{title} differences by scenario:\n")
            L.append("| Scenario | Missed | Extra |\n|---|---|---|")
            for d in block["diffs"]:
                L.append(f"| {d['scenario']} | {', '.join(d['missed']) or '-'} | {', '.join(d['extra']) or '-'} |")

    L.append("\n## 4. MOCK issuer verification status handling\n")
    L.append(f"Correct status: **{pct(ver['correct'], ver['total'])}** of verification requests.\n")
    L.append("| Expected | Actual | Count |\n|---|---|---|")
    for (e, a), n in sorted(ver["confusion"].items()):
        L.append(f"| {e} | {a} | {n} |")

    L.append("\n## 5. Hard examples\n")
    L.append("### 5a. Degraded scans (OCR)\n")
    if scans.get("skipped"):
        L.append("Skipped: Tesseract not available. Run inside Docker for these numbers.\n")
    else:
        L.append("| Scan quality | Fields exactly correct |\n|---|---|")
        for level, (ok, n) in scans["per_level"].items():
            L.append(f"| {level} | {pct(ok, n)} |")
        L.append("\nOCR'd values below 0.85 confidence are flagged for officer confirmation (EXT-001).\n")
    L.append("### 5b. Institution name matching (threshold 88)\n")
    L.append("| Case | Value | Should flag | Flagged | OK |\n|---|---|---|---|---|")
    for h in hard:
        L.append(f"| {h['case']} | {h['value']} | {h['should_flag']} | {h['flagged']} | {'yes' if h['correct'] else '**no**'} |")
    L.append("\nFuzzy matching cannot tell a near-identical name of a *different* institution from a typo. "
             "That is why name mismatches are findings for an officer, never automatic decisions, and why "
             "MOCK issuer verification compares names too.\n")

    L.append("## 6. Time per application (upload, extraction, analysis, verification, validation)\n")
    if timings:
        L.append(f"Median **{statistics.median(timings):.2f} s**, mean {statistics.mean(timings):.2f} s, "
                 f"max {max(timings):.2f} s over {len(timings)} applications (single process, SQLite, "
                 "this machine). Scans with OCR are the slowest.\n")
        slow = sorted(results, key=lambda r: -r["seconds"])[:3]
        L.append("Slowest: " + ", ".join(f"{r['scenario']} {r['seconds']:.2f} s" for r in slow) + ".\n")

    L.append("## 7. What these numbers do not show\n")
    L.append("- No real documents were used; layouts, fonts and wording are ours.\n"
             "- Every issuer source is MOCK; real issuer APIs will fail and disagree in other ways.\n"
             "- Rules and checklists are ILLUSTRATIVE, not the official AICTE handbook.\n"
             "- No user study: the time-saved counter is an assumption, not a measurement.\n")
    return "\n".join(L) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO_ROOT / "docs" / "eval-results.md"))
    args = parser.parse_args()
    manifest = generate_all(out_dir=OUT_DOCS)
    ext = evaluate_extraction(manifest)
    results, timings = run_scenarios(manifest)
    val, ano = score(results, anomaly=False), score(results, anomaly=True)
    ver = verification_table(results)
    signals = anomaly_signals(manifest)
    hard = hard_examples()
    scans = hard_scans()
    md = render(ext, val, ano, ver, signals, hard, timings, results, scans)
    out = Path(args.out)
    out.write_text(md, encoding="utf-8")
    raw = {"extraction": ext, "validation": val, "anomaly": ano,
           "verification": {"correct": ver["correct"], "total": ver["total"],
                            "confusion": [{"expected": e, "actual": a, "count": n} for (e, a), n in ver["confusion"].items()]},
           "signals": signals, "hard_examples": hard, "hard_scans": scans, "seconds_per_application": timings,
           "ocr_available": ocr_available()}
    out.with_suffix(".json").write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
