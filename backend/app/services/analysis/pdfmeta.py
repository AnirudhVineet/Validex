"""PDF structure and metadata signals (pikepdf). Deliberately conservative.

Normal Word / LibreOffice / scanner exports have ordinary creator and producer values, so we
do NOT flag those. We record:
- incremental updates (more than one %%EOF / startxref): the file was changed after it was saved
- creation and modification dates
- producer / creator matching a short list of image or PDF editing tools
- digital signature presence (detected only, never validated)
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pikepdf

EDITING_TOOLS = ("photoshop", "gimp", "illustrator", "pdf editor", "pdfescape", "sejda", "inkscape", "paint")
_PDF_DATE = re.compile(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?([+\-Z])?(\d{2})?'?(\d{2})?")


def parse_pdf_date(value: str | None) -> str | None:
    """'D:20261026120000+05'30'' -> ISO 8601 in UTC, or None."""
    if not value:
        return None
    m = _PDF_DATE.match(str(value))
    if not m:
        return None
    year, month, day, hour, minute, second = (int(g) if g else d for g, d in zip(m.groups()[:6], (0, 1, 1, 0, 0, 0)))
    try:
        dt = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None
    sign, tz_h, tz_m = m.group(7), m.group(8), m.group(9)
    if sign in ("+", "-") and tz_h:
        offset = timedelta(hours=int(tz_h), minutes=int(tz_m or 0))
        dt = dt - offset if sign == "+" else dt + offset
    return dt.replace(tzinfo=timezone.utc).isoformat()


def _has_signature(pdf: pikepdf.Pdf, raw: bytes) -> bool:
    acro = pdf.Root.get("/AcroForm")
    if acro is not None:
        for field in acro.get("/Fields", []):
            if field.get("/FT") == pikepdf.Name("/Sig"):
                return True
    return b"/ByteRange" in raw


def inspect(path: Path) -> dict:
    raw = path.read_bytes()
    with pikepdf.open(path) as pdf:
        info = pdf.docinfo
        producer = str(info.get("/Producer", "")) or None
        creator = str(info.get("/Creator", "")) or None
        tool_text = f"{producer or ''} {creator or ''}".lower()
        return {
            "pages": len(pdf.pages),
            "eof_markers": raw.count(b"%%EOF"),
            "incremental_updates": max(0, raw.count(b"startxref") - 1),
            "producer": producer,
            "creator": creator,
            "creation_date": parse_pdf_date(info.get("/CreationDate")),
            "mod_date": parse_pdf_date(info.get("/ModDate")),
            "editing_tool": next((t for t in EDITING_TOOLS if t in tool_text), None),
            "signature_present": _has_signature(pdf, raw),
        }
