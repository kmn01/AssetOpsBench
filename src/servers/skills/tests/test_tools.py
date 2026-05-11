import pytest

from servers.skills.main import mcp

from .conftest import call_tool


class TestListSkills:
    @pytest.mark.anyio
    async def test_list_skills_returns_entries(self):
        data = await call_tool(mcp, "list_skills", {})
        items = data["skills"]
        assert isinstance(items, list)
        assert data.get("catalog_error") in (None, "")
        assert any(
            isinstance(x, dict)
            and x.get("fqid") == "assetopsbench/pump_seal_inspection"
            for x in items
        )


class TestGetSkillManifest:
    @pytest.mark.anyio
    async def test_known_skill(self):
        data = await call_tool(
            mcp,
            "get_skill_manifest",
            {"skill_id": "assetopsbench/pump_seal_inspection"},
        )
        assert data.get("fqid") == "assetopsbench/pump_seal_inspection"
        assert "required_servers" in data
        assert "iot" in data["required_servers"]
        assert data.get("installed") is True
        assert data.get("runnable") is True

    @pytest.mark.anyio
    async def test_unknown_skill(self):
        data = await call_tool(
            mcp, "get_skill_manifest", {"skill_id": "vendor/nope"}
        )
        assert "error" in data


class TestRunSkill:
    @pytest.mark.anyio
    async def test_run_skill_pump_happy_path(self):
        from servers.skills.sibling_mcp import set_sibling_pool_for_testing

        from .fake_sibling import FakeSiblingMCPPool

        mapping = {
            ("iot", "sensors"): {
                "site_name": "MAIN",
                "asset_id": "P1",
                "total_sensors": 1,
                "sensors": ["Vibration"],
                "message": "ok",
            },
            ("fmsr", "get_failure_modes"): {
                "asset_name": "centrifugal pump",
                "failure_modes": ["Seal wear"],
            },
            ("wo", "get_work_orders"): {
                "equipment_id": "P1",
                "total": 1,
                "work_orders": [],
                "message": "ok",
            },
        }
        set_sibling_pool_for_testing(FakeSiblingMCPPool(mapping))
        data = await call_tool(
            mcp,
            "run_skill",
            {
                "skill_id": "assetopsbench/pump_seal_inspection",
                "arguments": {
                    "site_name": "MAIN",
                    "asset_id": "P1",
                    "asset_name": "centrifugal pump",
                },
            },
        )
        assert data.get("overall_ok") is True
        assert len(data.get("steps", [])) == 3
