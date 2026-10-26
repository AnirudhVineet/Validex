"""Render a document page to PNG for evidence highlighting in the UI."""
import io
from pathlib import Path

from PIL import Image

# PNG pixels per PDF point. bbox values (PDF points) multiply by this to land on the image.
PDF_SCALE = 2.0


def render_page_png(path: Path, mime: str, page: int) -> bytes | None:
    """PNG bytes for a 1-based page, or None if the page does not exist."""
    if page < 1:
        return None
    if mime == "application/pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        try:
            if page > len(pdf):
                return None
            img = pdf[page - 1].render(scale=PDF_SCALE).to_pil()
        finally:
            pdf.close()
    else:
        if page != 1:
            return None
        with Image.open(path) as src:
            img = src.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
