FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer fonts-dejavu fonts-liberation nodejs npm && rm -rf /var/lib/apt/lists/*
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt
COPY server /app/server
RUN npm install --prefix /app/server/ocr --omit=dev --ignore-scripts && node /app/server/ocr/setup-models.mjs /app/ocr-models
COPY .agents/skills/schimmelpilz-german-law /app/.agents/skills/schimmelpilz-german-law

ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data
ENV LEGAL_DATA_DIR=/data/legal-sources
ENV OCR_MODEL_DIR=/app/ocr-models
VOLUME ["/data"]
EXPOSE 8000
# The API is only reachable on the internal Compose network, behind Caddy, which replaces
# X-Forwarded-For with the real client address. Trusting it keeps login rate limits per visitor.
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
