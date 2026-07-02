"""Health check endpoint."""

from fastapi import APIRouter

from backend.collectors.health import collect_health
from .serialize import to_dict

router = APIRouter()


@router.get("/health")
async def get_health():
    return to_dict(collect_health())
