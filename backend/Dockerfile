# Build context is the repo root (see docker-compose.yml) so seed/ is available.
FROM python:3.12-slim

# Tesseract (OCR for scans) and zbar (QR decoding) for later phases.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libzbar0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY seed/ /app/seed/

EXPOSE 8000
# Seeding is idempotent, so running it on every start keeps "seed -> login" working.
CMD ["sh", "-c", "python /app/seed/seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
