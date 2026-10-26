"""QR code decoding with OpenCV. A decoded QR feeds the (MOCK) issuer verification gateway."""
import json

import cv2
import numpy as np
from PIL import Image

QR_DPI = 200  # enough for our noisy synthetic scans to decode


def _decode(img: Image.Image) -> str:
    arr = np.array(img)
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(arr)
    if not data:  # second try on a binarised image
        _, bw = cv2.threshold(cv2.medianBlur(arr, 3), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        data, _, _ = detector.detectAndDecode(bw)
    return data or ""


def parse_payload(text: str) -> dict:
    """Our MOCK issuers encode {"issuer": ..., "ref": ...}. Anything else is kept as raw text."""
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "ref" in data:
            return {"issuer": str(data.get("issuer", "")), "ref": str(data["ref"]), "raw": text}
    except ValueError:
        pass
    return {"issuer": None, "ref": None, "raw": text}


def decode_pages(pages: list[Image.Image]) -> list[dict]:
    """[{page, issuer, ref, raw}] for every page with a readable QR code."""
    found = []
    for page_no, img in enumerate(pages, start=1):
        text = _decode(img)
        if text:
            found.append({"page": page_no, **parse_payload(text)})
    return found
