FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kopiujemy requirements i instalujemy (kropka po spacji!)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy resztę plików (kropka, spacja, kropka!)
COPY . .

RUN mkdir -p /data && chmod 777 /data

ENV FERMA_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python3", "app.py"]