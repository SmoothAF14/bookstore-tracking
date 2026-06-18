FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8003

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# supervisord runs uvicorn + the Celery worker + Celery beat together in this
# single free-tier container (Render free tier has no separate worker service).
RUN pip install --no-cache-dir supervisor

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8003

CMD ["supervisord", "-c", "/app/supervisord.conf"]
