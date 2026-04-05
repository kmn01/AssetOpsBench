from unittest.mock import patch

import pytest

from servers.skills.main import mcp

from .conftest import call_tool


class TestListSkills:
    @pytest.mark.anyio
    async def test_list_skills_returns_entries(self):
        data = await call_tool(mcp, "list_skills", {})
        items = data["skills"]
        assert isinstance(items, list)
        assert any(
            isinstance(x, dict) and x.get("id") == "pump_seal_inspection" for x in items
        )


class TestGetSkillManifest:
    @pytest.mark.anyio
    async def test_known_skill(self):
        data = await call_tool(
            mcp, "get_skill_manifest", {"skill_id": "pump_seal_inspection"}
        )
        assert data.get("id") == "pump_seal_inspection"
        assert "required_servers" in data
        assert "iot" in data["required_servers"]
        assert data.get("enabled") is True

    @pytest.mark.anyio
    async def test_unknown_skill(self):
        data = await call_tool(mcp, "get_skill_manifest", {"skill_id": "nope"})
        assert "error" in data


class TestGetSkillsInheritance:
    @pytest.mark.anyio
    async def test_chiller_curated(self):
        data = await call_tool(mcp, "get_skills", {"asset_name": "Chiller 6"})
        assert "skills" in data
        assert len(data["skills"]) >= 1

    @pytest.mark.anyio
    async def test_unknown_asset_no_llm(self, no_llm_skills):
        data = await call_tool(mcp, "get_skills", {"asset_name": "ExoticUnit"})
        assert "error" in data


@pytest.fixture
def no_llm_skills():
    with patch("servers.skills.inheritance._llm_available", False):
        yield


class TestSkillInheritance:
    @pytest.mark.anyio
    async def test_requires_llm(self, no_llm_skills):
        data = await call_tool(
            mcp,
            "get_skill_inheritance",
            {"asset_name": "Chiller 6", "skill_name": "x"},
        )
        assert "error" in data

    @pytest.mark.anyio
    async def test_returns_parents_with_mock_chain(self):
        with patch(
            "servers.skills.inheritance._call_skill_inheritance_parents",
            return_value=["ParentA", "ParentB"],
        ):
            with patch("servers.skills.inheritance._llm_available", True):
                data = await call_tool(
                    mcp,
                    "get_skill_inheritance",
                    {"asset_name": "Chiller 6", "skill_name": "Inspect compressor"},
                )
        assert data.get("parent_skills") == ["ParentA", "ParentB"]
