import pytest

from servers.skills.registry import get_manifest_for_skill, list_skill_summaries


def test_list_skill_summaries_default_includes_pump_skill():
    items = list_skill_summaries()
    ids = {s.id for s in items}
    assert "pump_seal_inspection" in ids


def test_enabled_skills_allowlist_filters_list(monkeypatch):
    monkeypatch.setenv("ENABLED_SKILLS", "nonexistent_skill")
    assert list_skill_summaries() == []


def test_enabled_skills_allowlist_shows_match(monkeypatch):
    monkeypatch.setenv("ENABLED_SKILLS", "pump_seal_inspection")
    items = list_skill_summaries()
    assert len(items) == 1
    assert items[0].id == "pump_seal_inspection"


def test_get_manifest_unknown():
    r = get_manifest_for_skill("no_such")
    assert r.model_dump()["error"]


def test_get_manifest_disabled_when_not_in_allowlist(monkeypatch):
    monkeypatch.setenv("ENABLED_SKILLS", "other")
    r = get_manifest_for_skill("pump_seal_inspection")
    data = r.model_dump()
    assert "error" not in data
    assert data["enabled"] is False
