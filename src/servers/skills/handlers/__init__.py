"""Skill handlers keyed by fully qualified skill id."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .diagnostics import run_asset_diagnostics_bundle
from .pump import run_pump_seal_inspection
from .safety import run_safety_clearance_check

SkillHandler = Callable[[Any, dict], Awaitable[Any]]

HANDLERS: dict[str, SkillHandler] = {
    "assetopsbench/pump_seal_inspection": run_pump_seal_inspection,
    "assetopsbench_demo/asset_diagnostics_bundle": run_asset_diagnostics_bundle,
    "assetopsbench_demo/safety_clearance_check": run_safety_clearance_check,
}
