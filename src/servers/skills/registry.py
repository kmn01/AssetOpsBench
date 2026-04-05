"""Skill marketplace manifest loading and ENABLED_SKILLS filtering."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SkillManifestRecord(BaseModel):
    id: str
    version: str
    description: str
    required_servers: list[str] = Field(default_factory=list)
    asset_types: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    default_enabled: bool = True


class SkillSummary(BaseModel):
    id: str
    version: str
    description: str
    enabled: bool


class SkillManifestResponse(BaseModel):
    id: str
    version: str
    description: str
    required_servers: list[str]
    asset_types: list[str]
    keywords: list[str]
    default_enabled: bool
    enabled: bool


class MarketplaceError(BaseModel):
    error: str


_MANIFEST_PATH = Path(__file__).parent / "manifest.yaml"


def _parse_enabled_allowlist() -> frozenset[str] | None:
    raw = os.environ.get("ENABLED_SKILLS", "").strip()
    if not raw:
        return None
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


def _is_enabled(skill_id: str, record: SkillManifestRecord, allow: frozenset[str] | None) -> bool:
    if not record.default_enabled:
        return False
    if allow is None:
        return True
    return skill_id in allow


def load_manifest_records() -> list[SkillManifestRecord]:
    with _MANIFEST_PATH.open() as f:
        data = yaml.safe_load(f)
    entries = data.get("skills") if isinstance(data, dict) else data
    if not entries:
        return []
    return [SkillManifestRecord.model_validate(item) for item in entries]


def list_skill_summaries() -> list[SkillSummary]:
    allow = _parse_enabled_allowlist()
    out: list[SkillSummary] = []
    for rec in load_manifest_records():
        en = _is_enabled(rec.id, rec, allow)
        if en:
            out.append(
                SkillSummary(
                    id=rec.id,
                    version=rec.version,
                    description=rec.description.strip(),
                    enabled=True,
                )
            )
    return out


def get_manifest_for_skill(skill_id: str) -> SkillManifestResponse | MarketplaceError:
    allow = _parse_enabled_allowlist()
    for rec in load_manifest_records():
        if rec.id != skill_id:
            continue
        en = _is_enabled(rec.id, rec, allow)
        return SkillManifestResponse(
            id=rec.id,
            version=rec.version,
            description=rec.description.strip(),
            required_servers=list(rec.required_servers),
            asset_types=list(rec.asset_types),
            keywords=list(rec.keywords),
            default_enabled=rec.default_enabled,
            enabled=en,
        )
    return MarketplaceError(error=f"unknown skill id: {skill_id}")
