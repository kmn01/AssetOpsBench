"""Data models for the agent orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .plan_execute.metrics import PlanExecuteMetrics
from .plan_execute.models import Plan, StepResult


@dataclass
class OrchestratorResult:
    """Final result from the plan-execute orchestrator."""

    question: str
    answer: str
    plan: Plan
    history: list[StepResult]
    metrics: Optional[PlanExecuteMetrics] = None
