# Dockerfile — jeden obraz dla RPi (arm64) i PC/VPS (amd64)
FROM python:3.12-slim

ARG TARGETARCH
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# GPIO tylko na arm64 (RPi) - best effort, brak biblioteki nie psuje obrazu
RUN if [ "$TARGETARCH" = "arm64" ]; then \
      pip install --no-cache-dir lgpio || echo "lgpio niedostepne - GPIO lokalne wylaczone"; \
    fi

COPY *.py ./
RUN mkdir -p /data

ENV FERMA_DATA_DIR=/data \
    PYTHONUNBUFFERED=1

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["python", "app.py"]
