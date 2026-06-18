# bookstore-tracking

Delivery **tracking bot** for the Enterprise Book Store platform. Automates the
end-to-end tracking lifecycle of an order: from dispatch to out-for-delivery to
delivered. It uses the **Google Maps API (mock data only)** keyed off the
address the user provides, and an **orchestrated LLM** that intelligently
advances the tracking state and order status as the simulated shipment moves.

> **Status:** Initial scaffolding only. Files below are placeholders — no
> business logic is implemented yet.

## Responsibilities

- Generate a mock route/ETA from the user's delivery address (Google Maps API,
  mock data).
- Run an orchestrated LLM that decides the next tracking checkpoint and the
  corresponding order status transition.
- Emit tracking checkpoints consumed by `bookstore-delivery`'s delivery-status
  timeline and shown on the orders page.
- Schedule tracking-advance jobs on **Celery** and execute them asynchronously.

## Tech Stack

- **FastAPI** — ASGI web framework
- **Celery + Redis** — async task scheduling/execution (broker + result backend)
- **Pydantic v2** — data validation
- **OpenAI SDK** — OpenAI-compatible client (OpenRouter) for the orchestration LLM
- **httpx** — calls into the Django backend and the delivery service
- **Google Maps API** — mock routing/ETA data
- **Render** — hosting platform

## Architecture (planned)

```
app/
├── main.py                     FastAPI app + router wiring
├── celery_app.py               Celery application + beat schedule
├── core/
│   ├── config.py               Settings (pydantic-settings)
│   ├── llm.py                  Orchestration LLM client provider
│   ├── maps_client.py          Google Maps API client (mock data)
│   └── backend_client.py       httpx client for the Django backend
├── routers/
│   ├── health.py               GET /health
│   └── tracking.py             POST /tracking endpoints
├── services/
│   ├── orchestrator.py         LLM-driven tracking/order status transitions
│   └── tracking_service.py     Tracking checkpoint generation
├── tasks/
│   └── tracking_tasks.py       Celery tasks (advance tracking, recompute ETA)
└── schemas/                    Request/response models
```

## Local Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure environment file
cp .env.example .env

# 4. Start Redis (broker), the API, and a Celery worker (separate shells)
uvicorn app.main:app --reload --port 8003
celery -A app.celery_app worker --loglevel=info
celery -A app.celery_app beat --loglevel=info
```

## Deployment

Deploys on **Render free tier** via `render.yaml` (Blueprint) as a **single
Docker web service**. Render's free tier has no separate `worker` service and
no managed Redis, so — exactly like `bookstore-backend` — one container runs the
FastAPI app + Celery worker + Celery beat together under **supervisord**
(`supervisord.conf`), and Celery reuses the **shared Render Redis** instance via
`REDIS_URL` (the same Redis the Django backend uses). No new Redis is
provisioned.
