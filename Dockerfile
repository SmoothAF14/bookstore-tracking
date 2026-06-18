FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8003

# Default command runs the API. Override for the Celery worker/beat processes
# (see render.yaml), e.g. `celery -A app.celery_app worker --loglevel=info`.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
