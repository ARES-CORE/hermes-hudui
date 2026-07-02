"""Cron jobs endpoints."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.collectors.cron import collect_cron
from .serialize import to_dict

router = APIRouter()

_HERMES_BIN: str | None = shutil.which("hermes")


def _hermes() -> str:
    if not _HERMES_BIN:
        raise HTTPException(status_code=503, detail="hermes CLI not found")
    return _HERMES_BIN


def _run(action: str, job_id: str) -> None:
    result = subprocess.run(
        [_hermes(), "cron", action, job_id],
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip() or f"hermes cron {action} failed"
        raise HTTPException(status_code=500, detail=detail)


class CreateCronBody(BaseModel):
    schedule: str
    prompt: str | None = None
    name: str | None = None
    deliver: str | None = None
    repeat: int | None = None
    skills: list[str] = Field(default_factory=list)
    script: str | None = None
    workdir: str | None = None


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _run_create(body: CreateCronBody) -> None:
    schedule = _clean_optional(body.schedule)
    if not schedule:
        raise HTTPException(status_code=400, detail="schedule cannot be empty")

    prompt = _clean_optional(body.prompt)
    name = _clean_optional(body.name)
    deliver = _clean_optional(body.deliver)
    script = _clean_optional(body.script)
    workdir = _clean_optional(body.workdir)
    skills = [skill.strip() for skill in body.skills if skill.strip()]

    if body.repeat is not None and body.repeat < 1:
        raise HTTPException(status_code=400, detail="repeat must be a positive integer")

    if workdir and not Path(workdir).is_absolute():
        raise HTTPException(status_code=400, detail="workdir must be an absolute path")

    cmd = [_hermes(), "cron", "create"]
    if name:
        cmd.extend(["--name", name])
    if deliver:
        cmd.extend(["--deliver", deliver])
    if body.repeat is not None:
        cmd.extend(["--repeat", str(body.repeat)])
    for skill in skills:
        cmd.extend(["--skill", skill])
    if script:
        cmd.extend(["--script", script])
    if workdir:
        cmd.extend(["--workdir", workdir])
    cmd.append(schedule)
    if prompt:
        cmd.append(prompt)

    result = subprocess.run(
        cmd,
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip() or "hermes cron create failed"
        raise HTTPException(status_code=500, detail=detail)


@router.get("/cron")
async def get_cron():
    return to_dict(collect_cron())


@router.post("/cron")
def create_job(body: CreateCronBody):
    # Trust boundary: creating cron jobs can schedule Hermes to run in arbitrary workdirs.
    # Keep this HUD API bound to trusted localhost-only access.
    _run_create(body)
    return {"status": "ok"}


@router.post("/cron/{job_id}/pause")
def pause_job(job_id: str):
    _run("pause", job_id)
    return {"status": "ok"}


@router.post("/cron/{job_id}/resume")
def resume_job(job_id: str):
    _run("resume", job_id)
    return {"status": "ok"}


@router.post("/cron/{job_id}/run")
def run_job(job_id: str):
    _run("run", job_id)
    return {"status": "ok"}


@router.delete("/cron/{job_id}")
def delete_job(job_id: str):
    _run("remove", job_id)
    return {"status": "ok"}
