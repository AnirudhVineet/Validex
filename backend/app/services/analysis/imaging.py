"""Rasterise documents and compute perceptual page hashes for near-duplicate detection.

Measured on our synthetic set (hash_size=24, 576 bits, after denoise + content crop, 4 seeds x
5 doc types): the same document rescanned is 52-88 bits apart; different document types are
>= 106 apart. Different certificates on the SAME template can be as close as 56, so a hit means
"these pages look alike", never "this is a copy" (see docs/model-cards.md).
"""
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image, ImageOps

HASH_SIZE = 24


def rasterize(path: Path, mime: str, dpi: int, max_pages: int) -> list[Image.Image]:
    """Greyscale page images. PNG / JPEG uploads are a single page."""
    if mime == "application/pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        try:
            return [pdf[i].render(scale=dpi / 72).to_pil().convert("L") for i in range(min(len(pdf), max_pages))]
        finally:
            pdf.close()
    with Image.open(path) as img:
        return [img.convert("L")]


def _denoise_and_crop(img: Image.Image) -> Image.Image:
    arr = np.array(img)
    arr = cv2.medianBlur(arr, 5)
    _, arr = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    clean = Image.fromarray(arr)
    box = ImageOps.invert(clean).getbbox()
    return clean.crop(box) if box else clean


def page_hash(img: Image.Image) -> str:
    small = img.resize((max(1, img.width // 2), max(1, img.height // 2)))
    return str(imagehash.phash(_denoise_and_crop(small), hash_size=HASH_SIZE))


def hash_distance(a: str, b: str) -> int:
    return imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b)
