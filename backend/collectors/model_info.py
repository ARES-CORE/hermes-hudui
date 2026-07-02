"""Live model capabilities derived from ~/.hermes/config.yaml + models_dev_cache.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..cache import get_cached_or_compute
from .models import ModelCapabilities
from .utils import default_hermes_dir, load_yaml


def _read_config(hermes_path: Path) -> dict:
    cfg = hermes_path / "config.yaml"
    if not cfg.exists():
        return {}
    try:
        return load_yaml(cfg.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _read_models_cache(hermes_path: Path) -> dict:
    """Parse models_dev_cache.json — cached because it's ~1.8MB."""
    path = hermes_path / "models_dev_cache.json"

    def _compute() -> dict:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    return get_cached_or_compute(
        cache_key=f"models_dev_cache:{path}",
        compute_fn=_compute,
        file_paths=[path],
        ttl=3600,  # file only changes on a refresh tick
    )


def _lookup_model(cache: dict, provider: str, model: str) -> Optional[dict]:
    if not provider or not model:
        return None
    # Direct provider match.
    provider_entry = cache.get(provider) or cache.get(provider.lower())
    if isinstance(provider_entry, dict):
        models = provider_entry.get("models")
        if isinstance(models, dict):
            m = models.get(model)
            if isinstance(m, dict):
                return m
    # Fallback: scan all providers (user may have `provider=openai-codex` while
    # the model lives under `openai`).
    for entry in cache.values():
        if not isinstance(entry, dict):
            continue
        models = entry.get("models")
        if isinstance(models, dict) and model in models:
            m = models[model]
            if isinstance(m, dict):
                return m
    return None


def _do_collect(hermes_path: Path) -> ModelCapabilities:
    config = _read_config(hermes_path)
    model_cfg = config.get("model") if isinstance(config, dict) else None
    if isinstance(model_cfg, str):
        model_cfg = {"default": model_cfg}
    if not isinstance(model_cfg, dict):
        model_cfg = {}

    model = str(model_cfg.get("default") or model_cfg.get("model") or "").strip()
    provider = str(model_cfg.get("provider") or "").strip()

    try:
        config_ctx = int(model_cfg.get("context_length") or 0)
    except (TypeError, ValueError):
        config_ctx = 0

    caps = ModelCapabilities(
        model=model,
        provider=provider,
        config_context_length=config_ctx,
    )

    if not model:
        return caps

    entry = _lookup_model(_read_models_cache(hermes_path), provider, model)
    if entry is None:
        # No models.dev metadata — still return config-based info.
        caps.effective_context_length = config_ctx
        return caps

    caps.found = True
    caps.family = str(entry.get("family") or "")
    caps.supports_tools = bool(entry.get("tool_call"))
    caps.supports_reasoning = bool(entry.get("reasoning"))
    caps.supports_structured_output = bool(entry.get("structured_output"))
    # attachment=True means the model accepts image attachments → vision.
    caps.supports_vision = bool(entry.get("attachment"))

    limit = entry.get("limit") or {}
    if isinstance(limit, dict):
        try:
            caps.auto_context_length = int(limit.get("context") or 0)
        except (TypeError, ValueError):
            caps.auto_context_length = 0
        try:
            caps.max_output_tokens = int(limit.get("output") or 0)
        except (TypeError, ValueError):
            caps.max_output_tokens = 0

    caps.effective_context_length = max(config_ctx, caps.auto_context_length)

    cost = entry.get("cost") or {}
    if isinstance(cost, dict):
        def _f(k: str) -> Optional[float]:
            try:
                v = cost.get(k)
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None
        caps.cost_input_per_m = _f("input")
        caps.cost_output_per_m = _f("output")
        caps.cost_cache_read_per_m = _f("cache_read")

    caps.release_date = str(entry.get("release_date") or "")
    caps.knowledge_cutoff = str(entry.get("knowledge") or "")

    return caps


def collect_model_info(hermes_dir: Optional[str] = None) -> ModelCapabilities:
    hermes_path = Path(default_hermes_dir(hermes_dir))
    return get_cached_or_compute(
        cache_key=f"model_info:{hermes_path}",
        compute_fn=lambda: _do_collect(hermes_path),
        file_paths=[hermes_path / "config.yaml", hermes_path / "models_dev_cache.json"],
        ttl=60,
    )
