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
