import json

import pytest


@pytest.fixture(autouse=True)
def clear_skill_catalog_cache():
    from servers.skills.registry import clear_skill_catalog_cache as clear_cat

    clear_cat()
    yield
    clear_cat()


@pytest.fixture(autouse=True)
def skill_install_state_path(tmp_path, monkeypatch):
    """All skills tests use an isolated install state with bundled example FQIDs."""
    p = tmp_path / "skill_install.json"
    p.write_text(
        json.dumps(
            {
                "installed": [
                    "assetopsbench/pump_seal_inspection",
                    "assetopsbench_demo/asset_diagnostics_bundle",
                    "assetopsbench_demo/safety_clearance_check",
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))


@pytest.fixture(autouse=True)
def reset_sibling_test_pool():
    from servers.skills.sibling_mcp import set_sibling_pool_for_testing

    set_sibling_pool_for_testing(None)
    yield
    set_sibling_pool_for_testing(None)


async def call_tool(mcp_instance, tool_name: str, args: dict) -> dict:
    """Call an MCP tool and return parsed JSON response."""
    import json as json_module

    contents, _ = await mcp_instance.call_tool(tool_name, args)
    return json_module.loads(contents[0].text)