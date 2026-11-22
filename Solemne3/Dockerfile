# Imagen de los servicios Python del backend y del paso que prepara secretos y datos (backend/preparar.py).
FROM python:3.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY scripts/gateway-read.hcl .
