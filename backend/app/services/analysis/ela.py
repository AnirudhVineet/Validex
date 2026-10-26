"""Error level analysis (ELA) for JPEG uploads only.

Re-save the image at a known JPEG quality and look at how much each block changes. Regions
edited after the last save often recompress differently. ELA is noisy and easily fooled; it is
never applied to digital PDFs, and a hit is only a preliminary indicator for manual review.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops

RESAVE_QUALITY = 90
BLOCK = 16
# Calibrated on our synthetic JPEGs (see tests/test_analysis.py): clean pages stay well below.
RATIO_THRESHOLD = 6.0
MIN_BLOCK_MEAN = 4.0


def analyze(path: Path) -> dict:
    import io

    with Image.open(path) as img:
        original = img.convert("RGB")
    buf = io.BytesIO()
    original.save(buf, format="JPEG", quality=RESAVE_QUALITY)
    buf.seek(0)
    resaved = Image.open(buf).convert("RGB")
    diff = np.asarray(ImageChops.difference(original, resaved).convert("L"), dtype=np.float32)

    h, w = diff.shape
    h, w = h - h % BLOCK, w - w % BLOCK
    blocks = diff[:h, :w].reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK).mean(axis=(1, 3))
    # Ignore near-empty blocks (white paper) so the baseline reflects printed content.
    content = blocks[blocks > 0.5]
    baseline = float(np.median(content)) if content.size else 0.0
    top = float(blocks.max()) if blocks.size else 0.0
    ratio = top / baseline if baseline > 0 else 0.0
    suspicious = int(((blocks > baseline * RATIO_THRESHOLD) & (blocks > MIN_BLOCK_MEAN)).sum()) if baseline > 0 else 0
    by, bx = np.unravel_index(int(blocks.argmax()), blocks.shape) if blocks.size else (0, 0)
    return {
        "applicable": True,
        "baseline": round(baseline, 3),
        "max_block": round(top, 3),
        "ratio": round(ratio, 2),
        "suspicious_blocks": suspicious,
        "hotspot_bbox": [int(bx * BLOCK), int(by * BLOCK), int((bx + 1) * BLOCK), int((by + 1) * BLOCK)],
        "flag": bool(suspicious > 0 and ratio >= RATIO_THRESHOLD and top >= MIN_BLOCK_MEAN),
    }
