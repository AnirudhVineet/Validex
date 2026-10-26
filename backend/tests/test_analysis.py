"""Upload-time signals, including false-positive checks on clean documents."""
import itertools
import random
from datetime import date
from pathlib import Path

import pytest

from app.services.analysis import analyze_file
from app.services.analysis.imaging import hash_distance
from app.services.analysis.pdfmeta import parse_pdf_date
from seed import docgen
from tests.conftest import INSTITUTION

NEAR_DUP_THRESHOLD = 96  # must match ANO-002 in config/rules/core.yaml
INST = docgen.InstitutionData(INSTITUTION["name"], INSTITUTION["address"], INSTITUTION["aicte_ref"], "S", 12)


def _gen(doc_type, variant="valid", seed=1):
    return docgen.make_document(doc_type, variant, INST, date.today(), random.Random(seed))


def _analyze(tmp_path: Path, data: bytes, mime="application/pdf", name="f.pdf") -> dict:
    path = tmp_path / name
    path.write_bytes(data)
    return analyze_file(path, mime)


@pytest.mark.parametrize("variant", ["valid", "scanned"])
def test_qr_decoded_from_digital_and_scanned(tmp_path, variant):
    gen = _gen("fire_noc", variant)
    qr = _analyze(tmp_path, gen.pdf)["qr"]
    assert qr and qr[0]["ref"] == gen.qr_ref and qr[0]["issuer"] == "MOCK-FIRE"


def test_clean_pdfs_raise_no_metadata_signals(tmp_path):
    for doc_type in docgen.DOC_TYPES:
        pdf = _analyze(tmp_path, _gen(doc_type).pdf)["pdf"]
        assert pdf["incremental_updates"] == 0
        assert pdf["editing_tool"] is None
        assert pdf["signature_present"] is False


def test_altered_pdf_shows_incremental_update_and_editor(tmp_path):
    pdf = _analyze(tmp_path, _gen("fire_noc", "altered").pdf)["pdf"]
    assert pdf["incremental_updates"] == 1
    assert pdf["editing_tool"] == "pdf editor"
    assert pdf["mod_date"] > pdf["creation_date"]


def test_signature_presence_detected(tmp_path):
    assert _analyze(tmp_path, _gen("accreditation_certificate", "signed").pdf)["pdf"]["signature_present"] is True


def test_near_duplicate_threshold_separates_rescans_from_other_doc_types(tmp_path):
    for doc_type in docgen.DOC_TYPES:
        base = _gen(doc_type, seed=2)
        rescan = docgen.make_scanned(base.pdf, random.Random(3))
        h_base = _analyze(tmp_path, base.pdf)["page_hashes"][0]
        h_rescan = _analyze(tmp_path, rescan, name="r.pdf")["page_hashes"][0]
        assert hash_distance(h_base, h_rescan) <= NEAR_DUP_THRESHOLD, doc_type

    hashes = {t: _analyze(tmp_path, _gen(t, seed=7).pdf, name=f"{t}.pdf")["page_hashes"][0] for t in docgen.DOC_TYPES}
    for a, b in itertools.combinations(docgen.DOC_TYPES, 2):
        assert hash_distance(hashes[a], hashes[b]) > NEAR_DUP_THRESHOLD, (a, b)


def test_ela_only_for_jpeg_and_no_false_positive_on_clean_pages(tmp_path):
    assert "ela" not in _analyze(tmp_path, _gen("fire_noc").pdf)
    for doc_type in docgen.DOC_TYPES:
        for quality in (60, 80, 95):
            jpeg = docgen.to_jpeg(_gen(doc_type).pdf, quality)
            ela = _analyze(tmp_path, jpeg, "image/jpeg", "p.jpg")["ela"]
            assert ela["applicable"] and ela["flag"] is False, (doc_type, quality, ela)


def test_pdf_date_parsing():
    assert parse_pdf_date("D:20261026120000+05'30'") == "2026-10-26T06:30:00+00:00"
    assert parse_pdf_date("D:2026") == "2026-01-01T00:00:00+00:00"
    assert parse_pdf_date("garbage") is None
