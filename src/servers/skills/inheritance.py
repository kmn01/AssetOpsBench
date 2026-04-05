"""LLM-backed asset skill lists and inheritance prompts (legacy / research tools)."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import List, Union

import yaml
from pydantic import BaseModel

logger = logging.getLogger("skills-mcp-server")

_SKILLS_FILE = Path(__file__).parent / "skills.yaml"
with _SKILLS_FILE.open() as _f:
    _SKILLS: dict[str, list[str]] = yaml.safe_load(_f)

_ASSET2SKILLS_PROMPT = (
    "What are different skills for asset {asset_name}?\n"
    "Your response should be a numbered list with each skill on a new line. "
    "Please only list the skill name.\n"
    "For example: \n\n1. foo\n\n2. bar\n\n3. baz"
)

_SKILL_INHERITANCE_PROMPT = (
    "What is the inheritance hierarchy of the skill {skill_name} for asset type implied by {asset_name}?\n"
    "Your response should be a numbered list with each parent skill that {skill_name} "
    "inherits from on a new line. Please only list the skill name.\n"
    "For example: \n\n1. foo\n\n2. bar\n\n3. baz"
)

_DEFAULT_MODEL_ID = "watsonx/meta-llama/llama-3-3-70b-instruct"
_MAX_RETRIES = 3


def _parse_numbered_list(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        m = re.match(r"^\d+[\.\)]\s*(.+)", line.strip())
        if m:
            items.append(m.group(1).strip())
    return items


def _build_llm():
    from llm import LiteLLMBackend

    model_id = os.environ.get("SKILLS_MODEL_ID", _DEFAULT_MODEL_ID)
    if model_id.startswith("watsonx/"):
        missing = [
            v for v in ("WATSONX_APIKEY", "WATSONX_PROJECT_ID") if not os.environ.get(v)
        ]
        if missing:
            raise RuntimeError(f"Missing env vars for WatsonX: {missing}")
    else:
        missing = [
            v for v in ("LITELLM_API_KEY", "LITELLM_BASE_URL") if not os.environ.get(v)
        ]
        if missing:
            raise RuntimeError(f"Missing env vars for LiteLLM: {missing}")
    return LiteLLMBackend(model_id)


try:
    _llm = _build_llm()
    _llm_available = True
except Exception as _e:
    logger.warning("LLM unavailable (Skills inheritance will use curated data only): %s", _e)
    _llm = None
    _llm_available = False


class InheritanceError(BaseModel):
    error: str


class SkillsForAssetResult(BaseModel):
    asset_name: str
    skills: List[str]


class SkillInheritanceLineageResult(BaseModel):
    asset_name: str
    skill_name: str
    parent_skills: List[str]


def _call_asset2skills(asset_name: str) -> list[str]:
    prompt = _ASSET2SKILLS_PROMPT.format(asset_name=asset_name)
    last_exc: Exception | None = None
    for _ in range(_MAX_RETRIES):
        try:
            if _llm is None:
                raise RuntimeError("LLM not initialized")
            return _parse_numbered_list(_llm.generate(prompt))
        except Exception as exc:
            last_exc = exc
    assert last_exc is not None
    raise last_exc


def _call_skill_inheritance_parents(asset_name: str, skill_name: str) -> list[str]:
    prompt = _SKILL_INHERITANCE_PROMPT.format(
        asset_name=asset_name, skill_name=skill_name
    )
    last_exc: Exception | None = None
    for _ in range(_MAX_RETRIES):
        try:
            if _llm is None:
                raise RuntimeError("LLM not initialized")
            return _parse_numbered_list(_llm.generate(prompt))
        except Exception as exc:
            last_exc = exc
    assert last_exc is not None
    raise last_exc


def get_skills_for_asset(
    asset_name: str,
) -> Union[SkillsForAssetResult, InheritanceError]:
    asset_key = re.sub(r"\d+", "", asset_name).strip().lower()
    if not asset_key or asset_key == "none":
        return InheritanceError(error="asset_name is required")

    if asset_key in _SKILLS:
        return SkillsForAssetResult(
            asset_name=asset_name,
            skills=_SKILLS[asset_key],
        )

    if not _llm_available:
        return InheritanceError(error="LLM unavailable and asset not in local database")

    try:
        result = _call_asset2skills(asset_name)
        return SkillsForAssetResult(asset_name=asset_name, skills=result)
    except Exception as exc:
        logger.error("_call_asset2skills failed: %s", exc)
        return InheritanceError(error=str(exc))


def get_skill_inheritance_for_skill(
    asset_name: str,
    skill_name: str,
) -> Union[SkillInheritanceLineageResult, InheritanceError]:
    if not asset_name:
        return InheritanceError(error="asset_name is required")
    if not skill_name:
        return InheritanceError(error="skill_name is required")
    if not _llm_available:
        return InheritanceError(error="LLM unavailable")

    try:
        parents = _call_skill_inheritance_parents(asset_name, skill_name)
        return SkillInheritanceLineageResult(
            asset_name=asset_name,
            skill_name=skill_name,
            parent_skills=parents,
        )
    except Exception as exc:
        logger.error("_call_skill_inheritance_parents failed: %s", exc)
        return InheritanceError(error=str(exc))
