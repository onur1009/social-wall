FROM python:3.11-slim

WORKDIR /app

# Backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["python", "main.py"]
