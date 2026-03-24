FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Używamy cudzysłowów, aby parser nie miał wątpliwości co do argumentów
COPY "requirements.txt" "/app/requirements.txt"
RUN pip install --no-cache-dir -r /app/requirements.txt

# Kopiujemy wszystko z kontekstu do /app/
COPY "." "/app/"

RUN mkdir -p /data && chmod 777 /data

ENV FERMA_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

# Używamy pełnej ścieżki do pliku
CMD ["python3", "/app/app.py"]