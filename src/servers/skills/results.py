"""Structured skill execution results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillStepResult(BaseModel):
    """One step in a composed skill (e.g. one sibling MCP tool call)."""

    name: str
    ok: bool
    detail: dict = Field(default_factory=dict)


class SkillRunResult(BaseModel):
    """Unified result shape for ``run_skill``."""

    skill_id: str
    overall_ok: bool
    steps: list[SkillStepResult] = Field(default_factory=list)


class SkillInvocationError(BaseModel):
    """Fatal error before or instead of a normal skill run."""

    error: str
