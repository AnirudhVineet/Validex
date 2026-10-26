"""File-level analysis run once at upload: QR codes, page hashes, PDF structure / metadata,
signature presence and (JPEG only) error level analysis.

The results are stored on ApplicationDocument.analysis and read later by deterministic rule
checks. Nothing here decides anything: anomaly rules turn these signals into *preliminary
indicators* that require manual review.
"""
from pathlib import Path

from app.services.analysis import ela, imaging, pdfmeta, qr


def analyze_file(path: Path, mime: str) -> dict:
    """Return a JSON-serialisable dict of signals. Individual failures are recorded, not raised."""
    result: dict = {"errors": []}
    try:
        pages = imaging.rasterize(path, mime, dpi=qr.QR_DPI, max_pages=3)
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"rasterize: {type(exc).__name__}")
        pages = []

    result["qr"] = qr.decode_pages(pages)
    result["page_hashes"] = [imaging.page_hash(p) for p in pages]

    if mime == "application/pdf":
        try:
            result["pdf"] = pdfmeta.inspect(path)
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"pdf: {type(exc).__name__}")
    if mime == "image/jpeg":
        try:
            result["ela"] = ela.analyze(path)
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"ela: {type(exc).__name__}")
    return result
