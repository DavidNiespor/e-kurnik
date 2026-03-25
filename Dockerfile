FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Zależności najpierw (cache warstwy)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Wszystkie pliki .py bezpośrednio (bez podkatalogu app/)
COPY *.py .

RUN mkdir -p /data && chmod 777 /data

ENV FERMA_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

# Zwiększony start_period bo pandas/openpyxl wolno się ładują
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:5000/health || exit 1

EXPOSE 5000
CMD ["python3", "app.py"]
