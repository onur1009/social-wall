FROM python:3.11-slim

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyaları
COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

# Ortam değişkenleri
ENV HOST=0.0.0.0
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "main.py"]
