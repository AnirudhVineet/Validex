"""AI fallback reader for poor scans (Groq vision model). OFF by default.

Used only when a scan or photo could not be read well by OCR: a field is missing, OCR is
not confident, or OCR is not installed. The page image is sent to the vision model, which
returns the printed text for each field (or null). The results are SUGGESTIONS:

- stored with source `ai_vision`, confidence 0.60, `needs_confirmation = true`;
- the rule engine ignores them until an officer confirms or corrects the value;
- where the same text can be found in the OCR words, its page region is attached so the
  officer can see it highlighted on the document.

Only SYNTHETIC documents are used in this prototype. Enabling it sends page images to Groq.
"""
import base64
import io
from pathlib import Path

from rapidfuzz import fuzz

from app.config import settings
from app.services.extraction.parse import Line, ParsedField, _normalize_value, union_bbox
from app.services.llm import LLMUnavailable, chat_json

AI_CONFIDENCE = 0.60
RENDER_DPI = 150
LOCATE_MIN_SCORE = 85

SYSTEM = (
    "You read scanned certificates for a document-checking prototype. For each requested field, copy the "
    "text exactly as printed on the page. If a field is not visible or not readable, return null. Never "
    "guess, never infer a value from other fields, and never correct what is printed."
)


def _page_image_b64(path: Path, mime: str) -> str:
    """Page 1 as a base64 JPEG (kept small for the API)."""
    from PIL import Image

    if mime == "application/pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        try:
            img = pdf[0].render(scale=RENDER_DPI / 72).to_pil()
        finally:
            pdf.close()
    else:
        img = Image.open(path)
    img = img.convert("RGB")
    img.thumbnail((1700, 2200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def wanted_fields(doc_cfg: dict) -> list[str]:
    fields = list(doc_cfg.get("fields", {}))
    if doc_cfg.get("row_id_pattern"):
        fields.append("faculty_ids")
    return fields


def _schema(fields: list[str]) -> dict:
    return {"type": "object", "additionalProperties": False, "required": fields,
            "properties": {f: {"type": ["string", "null"]} for f in fields}}


def read_page(path: Path, mime: str, doc_label: str, fields: list[str], caller=None) -> dict[str, str | None]:
    """Ask the vision model for the printed value of each field. Raises LLMUnavailable."""
    if not fields:
        return {}
    descriptions = ", ".join(f.replace("_", " ") for f in fields)
    prompt = [
        {"type": "text", "text": (
            f"This is page 1 of a '{doc_label}'. Return a JSON object with these keys: {', '.join(fields)} "
            f"({descriptions}). For faculty_ids return every faculty ID in the table, comma-separated.")},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_page_image_b64(path, mime)}"}},
    ]
    call = caller or (lambda: chat_json(settings.vision_model, SYSTEM, prompt, "document_fields", _schema(fields)))
    data = call()
    return {f: (data.get(f) if isinstance(data.get(f), str) and data.get(f).strip() else None) for f in fields}


def _locate(value: str, lines: list[Line]) -> tuple[int | None, list[float] | None]:
    """Find the OCR line that contains the AI-read value, for evidence highlighting."""
    best, best_line = 0, None
    target = value.lower()
    for line in lines:
        score = fuzz.partial_ratio(target, line.text.lower())
        if score > best:
            best, best_line = score, line
    if best_line is None or best < LOCATE_MIN_SCORE:
        return None, None
    return best_line.page, union_bbox(best_line.words)


def merge(parsed: dict[str, ParsedField], ai_values: dict[str, str | None], lines: list[Line]) -> int:
    """Add AI suggestions for fields OCR missed or was unsure about. Confident OCR values are kept.
    Returns how many fields the AI supplied."""
    added = 0
    for name, raw in ai_values.items():
        if raw is None:
            continue
        current = parsed.get(name)
        if current is not None and not current.needs_confirmation:
            continue
        if name == "faculty_ids":
            ids = [x.strip().upper() for x in raw.replace(";", ",").split(",") if x.strip()]
            page, bbox = _locate(ids[0], lines) if ids else (None, None)
            parsed["faculty_ids"] = ParsedField("faculty_ids", ",".join(ids), AI_CONFIDENCE, page, bbox, True, "ai_vision")
            if "faculty_count" not in parsed or parsed["faculty_count"].needs_confirmation:
                parsed["faculty_count"] = ParsedField("faculty_count", str(len(ids)), AI_CONFIDENCE, page, bbox,
                                                      True, "ai_vision")
            added += 1
            continue
        value, _ = _normalize_value(name, raw)
        page, bbox = _locate(raw, lines)
        parsed[name] = ParsedField(name, value, AI_CONFIDENCE, page, bbox, True, "ai_vision")
        added += 1
    return added


def needs_help(parsed: dict[str, ParsedField], doc_cfg: dict) -> bool:
    expected = set(doc_cfg.get("fields", {}))
    if doc_cfg.get("row_id_pattern"):
        expected.add("faculty_count")
    return any(name not in parsed or parsed[name].needs_confirmation for name in expected)


__all__ = ["LLMUnavailable", "merge", "needs_help", "read_page", "wanted_fields"]
