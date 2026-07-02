"""Prompt patterns endpoint."""

from fastapi import APIRouter

from backend.collectors.patterns import collect_patterns
from .serialize import to_dict

router = APIRouter()


@router.get("/patterns")
async def get_patterns():
    return to_dict(collect_patterns())
