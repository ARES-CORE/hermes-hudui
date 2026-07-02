"""Corrections endpoint."""

from fastapi import APIRouter

from backend.collectors.corrections import collect_corrections
from .serialize import to_dict

router = APIRouter()


@router.get("/corrections")
async def get_corrections():
    return to_dict(collect_corrections())
