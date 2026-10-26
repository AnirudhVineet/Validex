"""Turn positioned words into lines, a document-type guess and labelled fields.

Deterministic: label matching with rapidfuzz plus regexes. Every field keeps the page and
bounding box of the words its value came from, so findings can highlight evidence later.
"""
import re
from dataclasses import dataclass
from datetime import datetime

from rapidfuzz import fuzz

from app.services.extraction.words import Word

LABEL_MATCH_THRESHOLD = 85
OCR_CONFIRM_BELOW = 0.85
DATE_FIELDS = {"issue_date", "expiry_date"}
_DATE_FORMATS = ["%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y"]


@dataclass
class Line:
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def page(self) -> int:
        return self.words[0].page


@dataclass
class ParsedField:
    name: str
    value: str | None
    confidence: float
    page: int | None
    bbox: list[float] | None
    needs_confirmation: bool
    source: str | None = None  # None = same as the document's extraction method; "ai_vision" for AI suggestions


def group_lines(words: list[Word]) -> list[Line]:
    """Group words into reading-order lines by page and vertical position.

    OCR words carry Tesseract's own line ids, which survive slightly rotated scans (a skewed line
    drifts several points from left to right), so those are grouped by id instead of position.
    """
    if words and all(w.line_key is not None for w in words):
        groups: dict[tuple, list[Word]] = {}
        for w in words:
            groups.setdefault((w.page, *w.line_key), []).append(w)
        ocr_lines = [Line(sorted(ws, key=lambda w: w.x0)) for ws in groups.values()]
        return sorted(ocr_lines, key=lambda ln: (ln.page, min(w.top for w in ln.words)))
    lines: list[Line] = []
    for w in sorted(words, key=lambda w: (w.page, w.top, w.x0)):
        if lines:
            last = lines[-1]
            ref = last.words[0]
            tolerance = max(3.0, 0.5 * (ref.bottom - ref.top))
            if w.page == ref.page and abs(w.top - ref.top) <= tolerance:
                last.words.append(w)
                continue
        lines.append(Line([w]))
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    return lines


def union_bbox(words: list[Word]) -> list[float]:
    return [round(min(w.x0 for w in words), 1), round(min(w.top for w in words), 1),
            round(max(w.x1 for w in words), 1), round(max(w.bottom for w in words), 1)]


def classify(lines: list[Line], doc_types: dict) -> str | None:
    """Keyword score per doc type; title lines (first 5) count three times. None if no match."""
    scores: dict[str, int] = {}
    for i, line in enumerate(lines):
        text = line.text.lower()
        weight = 3 if i < 5 else 1
        for doc_type, cfg in doc_types.items():
            hits = sum(text.count(k) for k in cfg.get("keywords", []))
            scores[doc_type] = scores.get(doc_type, 0) + weight * hits
    best = max(scores, key=scores.get, default=None)
    return best if best and scores[best] > 0 else None


def _normalize_label(text: str) -> str:
    return " ".join(re.sub(r"[^a-z ]", " ", text.lower()).split())


def _split_label_value(line: Line) -> tuple[str, str, list[Word]] | None:
    """Split 'Label: value' into (label, value, value_words). OCR may read ':' as ';'."""
    for i, word in enumerate(line.words):
        m = re.search(r"[:;]", word.text)
        if not m:
            continue
        label = " ".join([w.text for w in line.words[:i]] + [word.text[:m.start()]])
        rest = word.text[m.end():]
        value_words = ([word] if rest else []) + line.words[i + 1:]
        value = " ".join(([rest] if rest else []) + [w.text for w in line.words[i + 1:]]).strip()
        return label, value, value_words
    return None


def normalize_date(raw: str) -> str | None:
    """Return ISO yyyy-mm-dd, or None if the date cannot be parsed."""
    text = re.sub(r"\s*([-/.])\s*", r"\1", raw.strip()).rstrip(".")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalize_value(name: str, raw: str) -> tuple[str, bool]:
    """(normalized value, parsed_ok)."""
    value = " ".join(raw.split())
    if name in DATE_FIELDS:
        iso = normalize_date(value)
        return (iso, True) if iso else (value, False)
    if name == "certificate_number":
        # IDs never start or end with punctuation; OCR specks often add a trailing "." or "-".
        return re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", value.replace(" ", "")).upper(), True
    if name == "land_area_acres":
        m = re.search(r"\d+(\.\d+)?", value)
        return (m.group(0), True) if m else (value, False)
    return value, True


def extract_fields(lines: list[Line], doc_cfg: dict, from_ocr: bool) -> dict[str, ParsedField]:
    """Find 'Label: value' lines whose label matches the configured labels for this doc type."""
    found: dict[str, tuple[int, ParsedField]] = {}  # field -> (label score, field)
    for line in lines:
        split = _split_label_value(line)
        if split is None:
            continue
        label, value, value_words = split
        label_norm = _normalize_label(label)
        if not label_norm or not value or not value_words:
            continue
        for name, candidates in doc_cfg.get("fields", {}).items():
            score = max(fuzz.ratio(label_norm, c) for c in candidates)
            if score < LABEL_MATCH_THRESHOLD or (name in found and found[name][0] >= score):
                continue
            normalized, ok = _normalize_value(name, value)
            base = sum(w.conf for w in value_words) / len(value_words) if from_ocr else 0.98
            confidence = round(base * score / 100 * (1.0 if ok else 0.5), 3)
            needs_confirmation = (not ok) or (from_ocr and confidence < OCR_CONFIRM_BELOW)
            found[name] = (score, ParsedField(name, normalized, confidence, line.page,
                                              union_bbox(value_words), needs_confirmation))
    fields = {name: pf for name, (_, pf) in found.items()}

    pattern = doc_cfg.get("row_id_pattern")
    if pattern:
        fields.update(_table_rows(lines, pattern, from_ocr))
    return fields


def _fix_ocr_digits(text: str) -> str:
    # Common OCR confusions inside the numeric part of an ID.
    return text.translate(str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1"}))


def _table_rows(lines: list[Line], pattern: str, from_ocr: bool) -> dict[str, ParsedField]:
    """Count table rows whose text contains an ID matching `pattern` (e.g. faculty IDs)."""
    prefix, _, _ = pattern.partition("[")
    loose = re.compile(re.escape(prefix) + r"[0-9OolI]{6}")
    ids: list[str] = []
    row_words: list[Word] = []
    for line in lines:
        for m in loose.finditer(line.text):
            fid = prefix + _fix_ocr_digits(m.group(0)[len(prefix):])
            if re.fullmatch(pattern, fid) and fid not in ids:
                ids.append(fid)
                row_words += line.words
    if not ids:
        return {}
    conf = (sum(w.conf for w in row_words) / len(row_words)) if from_ocr else 0.98
    page = row_words[0].page
    bbox = union_bbox([w for w in row_words if w.page == page])
    needs = from_ocr and conf < OCR_CONFIRM_BELOW
    return {
        "faculty_count": ParsedField("faculty_count", str(len(ids)), round(conf, 3), page, bbox, needs),
        "faculty_ids": ParsedField("faculty_ids", ",".join(ids), round(conf, 3), page, bbox, needs),
    }
