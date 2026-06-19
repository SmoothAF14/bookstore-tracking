"""
main.py — FastAPI application entrypoint for the delivery tracking bot.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import health, tracking

app = FastAPI(
    title="Enterprise Book Store — Delivery Tracking Bot",
    description=(
        "Automates the shipment tracking lifecycle (dispatch → in transit → "
        "out for delivery → delivered) using mock Google Maps route/ETA data "
        "and an orchestrated LLM that advances tracking + order status."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(tracking.router, prefix="/tracking", tags=["Tracking"])
