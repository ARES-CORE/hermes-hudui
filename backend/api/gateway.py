"""Gateway status + action endpoints."""

from fastapi import APIRouter, HTTPException

from backend.collectors.gateway import (
    ACTION_NAMES,
    collect_gateway_status,
    read_action_status,
    run_action,
)
from .serialize import to_dict

router = APIRouter()


@router.get("/gateway")
async def get_gateway():
    return to_dict(collect_gateway_status())


@router.post("/gateway/restart")
async def restart_gateway():
    try:
        return run_action("gateway-restart")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hermes/update")
async def update_hermes():
    try:
        return run_action("hermes-update")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions/{name}/status")
async def action_status(name: str):
    if name not in ACTION_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown action: {name}")
    return read_action_status(name)
