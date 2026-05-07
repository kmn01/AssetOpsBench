"""WandB configuration from environment variables.

Variable names follow common WANDB_* conventions so ``wandb login`` and the
SDK pick up ``WANDB_API_KEY``, ``WANDB_ENTITY``, etc. when unset here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _truthy(val: str | None) -> bool:
    if val is None or not val.strip():
        return False
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class WandbSettings:
    """Effective WandB options for AssetOpsBench."""

    enabled: bool
    project: str | None
    entity: str | None
    group: str | None
    tags: tuple[str, ...]
    mode: str | None
    run_name: str | None
    job_type_default: str | None
    log_each_plan_execute: bool


def load_wandb_settings() -> WandbSettings:
    """Read settings from ``os.environ`` (call after ``load_dotenv()``)."""
    tags_raw = (os.environ.get("WANDB_TAGS") or "").strip()
    tags = tuple(t.strip() for t in tags_raw.split(",") if t.strip())
    mode = (os.environ.get("WANDB_MODE") or "").strip() or None
    if mode is not None and mode.lower() == "disabled":
        mode = "disabled"
    return WandbSettings(
        enabled=_truthy(os.environ.get("WANDB_ENABLED")),
        project=(os.environ.get("WANDB_PROJECT") or "").strip() or None,
        entity=(os.environ.get("WANDB_ENTITY") or "").strip() or None,
        group=(os.environ.get("WANDB_GROUP") or "").strip() or None,
        tags=tags,
        mode=mode,
        run_name=(os.environ.get("WANDB_RUN_NAME") or "").strip() or None,
        job_type_default=(os.environ.get("WANDB_JOB_TYPE") or "").strip() or None,
        log_each_plan_execute=_truthy(os.environ.get("WANDB_LOG_EACH_PLAN_EXECUTE")),
    )


def wandb_requirements_satisfied(settings: WandbSettings) -> bool:
    """Return False if WandB is enabled but required fields are missing."""
    if not settings.enabled:
        return True
    return bool(settings.project)
