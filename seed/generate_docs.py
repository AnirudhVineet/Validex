"""Generate SYNTHETIC documents for every seed scenario plus demo-upload files, and a manifest
of expected findings for evaluation.

Run from the repo root:  backend/.venv/Scripts/python seed/generate_docs.py
Output (git-ignored):    seed/output/
  applications/<scenario>/<doc_type>__<variant>.pdf
  demo_upload/<doc_type>__<variant>.pdf      (for the demo applicant to upload live)
  manifest.json                              (truth values + expected rule ids per document / scenario)
  mock_issuer_data.json                      (MOCK issuer records for QR references)
"""
import json
import random
import sys
from datetime import date
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SEED_DIR.parent))

from seed.data import DEMO_UPLOADS, SCENARIOS, build_institutions  # noqa: E402
from seed.docgen import InstitutionData, make_document  # noqa: E402

OUTPUT_DIR = SEED_DIR / "output"


def _inst_data(inst: dict) -> InstitutionData:
    return InstitutionData(inst["name"], inst["address"], inst["aicte_ref"], inst["state"], inst["faculty_count"])


def _write(path: Path, gen, inst: dict, manifest: list, issuer_records: dict, scenario: str | None, out_dir: Path,
           issuer_sim: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gen.pdf)
    manifest.append({
        "file": path.relative_to(out_dir).as_posix(), "scenario": scenario,
        "institution_ref": inst["aicte_ref"], "doc_type": gen.doc_type, "variant": gen.variant,
        "truth": gen.truth, "expected_rule_ids": gen.expected_rule_ids, "qr_ref": gen.qr_ref,
    })
    if gen.qr_ref:
        # The MOCK issuer holds what it actually issued: the real institution name, even when the
        # document copy shows another name (name_mismatch variant).
        issuer_records[gen.qr_ref] = {
            "issuer": gen.issuer, "is_mock": True, "institution_name": inst["name"], "status": "valid",
            **{k: v for k, v in gen.truth.items() if k in ("certificate_number", "issue_date", "expiry_date")},
            **gen.issuer_overrides,     # e.g. the real expiry for an "altered" document
            **(issuer_sim or {}),       # e.g. {"status": "pending"} or {"simulate": "timeout"}
        }


def generate_all(today: date | None = None, out_dir: Path = OUTPUT_DIR) -> dict:
    today = today or date.today()
    institutions = build_institutions()
    documents: list[dict] = []
    issuer_records: dict = {}
    applications = []
    rng = random.Random(2026)
    files_by_scenario: dict[str, dict[str, str]] = {}
    faculty_by_scenario: dict[str, list[str]] = {}

    for sc in SCENARIOS:
        inst = institutions[sc["institution"]]
        files = []
        for doc_type, variant in sc["docs"].items():
            if doc_type in sc.get("copy_from", {}):  # byte-identical file from another scenario
                files.append({"doc_type": doc_type, "file": files_by_scenario[sc["copy_from"][doc_type]][doc_type]})
                continue
            faculty = None
            if doc_type == "faculty_list" and sc.get("faculty_ratio"):
                faculty = round(inst["faculty_count"] * sc["faculty_ratio"])
            shared = None
            if doc_type == "faculty_list" and sc.get("share_faculty_from"):
                shared = faculty_by_scenario[sc["share_faculty_from"]][: sc.get("shared_faculty", 5)]
            gen = make_document(doc_type, variant, _inst_data(inst), today, rng, faculty_count=faculty,
                                shared_faculty_ids=shared)
            if doc_type == "faculty_list":
                faculty_by_scenario[sc["key"]] = gen.truth["faculty_ids"].split(",")
            path = out_dir / "applications" / sc["key"] / f"{doc_type}__{variant}.pdf"
            _write(path, gen, inst, documents, issuer_records, sc["key"], out_dir, sc.get("issuer_sim", {}).get(doc_type))
            files.append({"doc_type": doc_type, "file": path.relative_to(out_dir).as_posix()})
        files_by_scenario[sc["key"]] = {f["doc_type"]: f["file"] for f in files}
        if sc.get("duplicate"):  # the same file uploaded into a second slot
            src = next(f for f in files if f["doc_type"] == sc["duplicate"]["from"])
            files = [f for f in files if f["doc_type"] != sc["duplicate"]["to"]]
            files.append({"doc_type": sc["duplicate"]["to"], "file": src["file"]})
        form_data = {}
        if sc.get("form_data_increase"):
            form_data["requested_intake"] = inst["approved_intake"] + sc["form_data_increase"]
        applications.append({"scenario": sc["key"], "institution_ref": inst["aicte_ref"],
                             "category": sc["category"], "form_data": form_data, "documents": files,
                             "target_status": sc["target"], "expected_rule_ids": sc["expected"],
                             "needs_ocr": sc.get("needs_ocr", False),
                             "backdate_pending_hours": sc.get("backdate_pending_hours"), "note": sc.get("note")})

    demo = institutions[0]
    for doc_type, variant in DEMO_UPLOADS:
        gen = make_document(doc_type, variant, _inst_data(demo), today, rng)
        _write(out_dir / "demo_upload" / f"{doc_type}__{variant}.pdf", gen, demo, documents, issuer_records, None, out_dir)

    manifest = {
        "synthetic": True,
        "notice": "All documents are SYNTHETIC and generated for prototype testing.",
        "generated_for_date": today.isoformat(),
        "documents": documents,
        "applications": applications,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "mock_issuer_data.json").write_text(
        json.dumps({"is_mock": True, "records": issuer_records}, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = generate_all()
    print(f"Generated {len(m['documents'])} SYNTHETIC documents for {len(m['applications'])} scenarios "
          f"in {OUTPUT_DIR}")
