"""
routers/health.py — Health check endpoint (used by Render's health probe).
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health_check():
    return {"status": "ok"}
