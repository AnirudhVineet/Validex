"""Word-level text with positions, from the PDF text layer (pdfplumber) or OCR (Tesseract).

All coordinates are PDF points with origin at the top-left of the page. For PNG / JPEG
uploads (no PDF page size) coordinates are image pixels, documented in CONTRACTS.md.
"""
import functools
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

OCR_DPI = 200


@dataclass
class Word:
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    page: int          # 1-based
    conf: float        # 0..1 (1.0 for the PDF text layer)
    line_key: tuple | None = None  # OCR only: Tesseract's (block, paragraph, line) - robust to skew


def pdf_text_words(path: Path) -> tuple[list[Word], int]:
    """Words from the PDF text layer and the page count."""
    words: list[Word] = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            for w in page.extract_words():
                words.append(Word(w["text"], float(w["x0"]), float(w["top"]),
                                  float(w["x1"]), float(w["bottom"]), page_no, 1.0))
        return words, len(pdf.pages)


@functools.lru_cache(maxsize=1)
def ocr_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001 - any failure means OCR is unavailable
        return False


def _ocr_image(image, page_no: int, scale: float) -> list[Word]:
    import pytesseract

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    words = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        words.append(Word(text, x * scale, y * scale, (x + w) * scale, (y + h) * scale,
                          page_no, conf / 100.0, line_key))
    return words


def ocr_pdf_words(path: Path) -> list[Word]:
    """Rasterise each PDF page and OCR it. Coordinates are converted back to PDF points."""
    import pypdfium2 as pdfium

    words: list[Word] = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        for page_no in range(len(pdf)):
            image = pdf[page_no].render(scale=OCR_DPI / 72).to_pil()
            words += _ocr_image(image, page_no + 1, 72 / OCR_DPI)
    finally:
        pdf.close()
    return words


def ocr_image_words(path: Path) -> list[Word]:
    from PIL import Image

    with Image.open(path) as img:
        return _ocr_image(img.convert("RGB"), 1, 1.0)
