import json

import pytest

from servers.skills.registry import (
    MarketplaceLoadError,
    SkillManifestView,
    coerce_skill_fqid,
    get_manifest_for_fqid,
    list_skill_items,
    maybe_bootstrap_install_state,
    merge_pack_records,
)


def test_list_skill_items_includes_pump_fqid():
    items = list_skill_items()
    fqids = {s.fqid for s in items}
    assert "assetopsbench/pump_seal_inspection" in fqids


def test_coerce_skill_fqid_bare_suffix():
    assert (
        coerce_skill_fqid("safety_clearance_check")
        == "assetopsbench_demo/safety_clearance_check"
    )
    assert coerce_skill_fqid("assetopsbench/pump_seal_inspection") == (
        "assetopsbench/pump_seal_inspection"
    )


def test_get_manifest_accepts_bare_skill_id():
    r = get_manifest_for_fqid("safety_clearance_check")
    assert isinstance(r, SkillManifestView)
    assert r.fqid == "assetopsbench_demo/safety_clearance_check"


def test_bootstrap_skipped_when_disabled(monkeypatch, tmp_path):
    # Not conftest's ``skill_install.json`` — that file is always created by autouse.
    dst = tmp_path / "bootstrap_target.json"
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(dst))
    monkeypatch.setenv("SKILL_BOOTSTRAP_INSTALL", "0")
    maybe_bootstrap_install_state()
    assert not dst.is_file()


def test_bootstrap_creates_file_when_enabled(monkeypatch, tmp_path):
    dst = tmp_path / "bootstrap_target.json"
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(dst))
    monkeypatch.setenv("SKILL_BOOTSTRAP_INSTALL", "1")
    assert not dst.is_file()
    maybe_bootstrap_install_state()
    data = json.loads(dst.read_text(encoding="utf-8"))
    assert "assetopsbench/pump_seal_inspection" in data["installed"]
    assert "assetopsbench_demo/safety_clearance_check" in data["installed"]


def test_bootstrap_does_not_overwrite_existing(monkeypatch, tmp_path):
    dst = tmp_path / "bootstrap_target.json"
    dst.write_text(
        json.dumps({"installed": ["custom/pack_only"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(dst))
    monkeypatch.setenv("SKILL_BOOTSTRAP_INSTALL", "1")
    maybe_bootstrap_install_state()
    data = json.loads(dst.read_text(encoding="utf-8"))
    assert data["installed"] == ["custom/pack_only"]


def test_installed_and_runnable_default(tmp_path, monkeypatch):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"installed": []}), encoding="utf-8")
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    row = next(
        x
        for x in list_skill_items()
        if x.fqid == "assetopsbench/pump_seal_inspection"
    )
    assert row.installed is False
    assert row.runnable is False


def test_enabled_skills_allowlist_filters_runnable(tmp_path, monkeypatch):
    p = tmp_path / "full.json"
    p.write_text(
        json.dumps(
            {
                "installed": [
                    "assetopsbench/pump_seal_inspection",
                    "assetopsbench_demo/safety_clearance_check",
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    monkeypatch.setenv(
        "ENABLED_SKILLS",
        "assetopsbench_demo/safety_clearance_check",
    )
    by_fq = {x.fqid: x for x in list_skill_items()}
    assert by_fq["assetopsbench/pump_seal_inspection"].installed is True
    assert by_fq["assetopsbench/pump_seal_inspection"].runnable is False
    assert (
        by_fq["assetopsbench_demo/safety_clearance_check"].runnable is True
    )


def test_enabled_skills_allowlist_normalizes_bare_suffix(tmp_path, monkeypatch):
    p = tmp_path / "st.json"
    p.write_text(
        json.dumps({"installed": ["assetopsbench/pump_seal_inspection"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    monkeypatch.setenv("ENABLED_SKILLS", "pump_seal_inspection")
    row = next(
        x
        for x in list_skill_items()
        if x.fqid == "assetopsbench/pump_seal_inspection"
    )
    assert row.runnable is True


def test_read_installed_coerces_bare_ids(tmp_path, monkeypatch):
    p = tmp_path / "st.json"
    p.write_text(
        json.dumps({"installed": ["pump_seal_inspection"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    row = next(
        x
        for x in list_skill_items()
        if x.fqid == "assetopsbench/pump_seal_inspection"
    )
    assert row.installed is True


def test_enabled_skills_empty_no_extra_allowlist(tmp_path, monkeypatch):
    p = tmp_path / "one.json"
    p.write_text(
        json.dumps({"installed": ["assetopsbench/pump_seal_inspection"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    monkeypatch.delenv("ENABLED_SKILLS", raising=False)
    row = next(
        x
        for x in list_skill_items()
        if x.fqid == "assetopsbench/pump_seal_inspection"
    )
    assert row.runnable is True


def test_get_manifest_unknown():
    r = get_manifest_for_fqid("unknown/pack")
    assert r.model_dump().get("error")


def test_get_manifest_shows_runnable_false_when_not_installed(tmp_path, monkeypatch):
    p = tmp_path / "none.json"
    p.write_text(json.dumps({"installed": []}), encoding="utf-8")
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    r = get_manifest_for_fqid("assetopsbench/pump_seal_inspection")
    data = r.model_dump()
    assert "error" not in data
    assert data["installed"] is False
    assert data["runnable"] is False


def test_merge_duplicate_fqid_raises(tmp_path, monkeypatch):
    bad = tmp_path / "pack_a"
    bad.mkdir()
    (bad / "manifest.yaml").write_text(
        "pack_id: dup\nskills:\n  - id: x\n    version: \"1\"\n    description: a\n",
        encoding="utf-8",
    )
    bad_b = tmp_path / "pack_b"
    bad_b.mkdir()
    (bad_b / "manifest.yaml").write_text(
        "pack_id: dup\nskills:\n  - id: x\n    version: \"1\"\n    description: b\n",
        encoding="utf-8",
    )
    from servers.skills import registry as reg

    monkeypatch.setenv("SKILL_PACK_DIRS", f"{bad},{bad_b}")

    def fake_bundled() -> object:
        nb = tmp_path / "nonexistent_bundled_xyz"
        nb.mkdir(exist_ok=True)
        return nb

    monkeypatch.setattr(reg, "bundled_packs_root", fake_bundled)
    with pytest.raises(MarketplaceLoadError, match="duplicate"):
        merge_pack_records()
