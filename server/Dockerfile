FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer fonts-dejavu fonts-liberation && rm -rf /var/lib/apt/lists/*
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt
COPY server /app/server
COPY .agents/skills/schimmelpilz-german-law /app/.agents/skills/schimmelpilz-german-law

ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data
ENV LEGAL_DATA_DIR=/data/legal-sources
VOLUME ["/data"]
EXPOSE 8000
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
