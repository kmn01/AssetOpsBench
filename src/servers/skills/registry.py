"""Skill marketplace: pack merge (FQID), install state, discovery flags."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

FQID_SEP = "/"

_log = logging.getLogger(__name__)

# Process-local cache; tests should call :func:`clear_skill_catalog_cache` when merge inputs change.
_catalog_cache: tuple[SkillRecord, ...] | None = None


class MarketplaceLoadError(RuntimeError):
    """Raised when pack merge rules are violated (e.g. duplicate FQID)."""


class SkillPackRecord(BaseModel):
    """One skill row from a pack manifest (before FQID)."""

    id: str
    version: str
    description: str
    required_servers: list[str] = Field(default_factory=list)
    asset_types: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    default_enabled: bool = True


class SkillRecord(BaseModel):
    """Merged catalog row with stable FQID ``pack_id/skill_id``."""

    fqid: str
    pack_id: str
    skill_id: str
    version: str
    description: str
    required_servers: list[str] = Field(default_factory=list)
    asset_types: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    default_enabled: bool = True


class SkillListItem(BaseModel):
    """One row returned by ``list_skills``."""

    fqid: str
    pack_id: str
    skill_id: str
    version: str
    description: str
    required_servers: list[str]
    asset_types: list[str]
    keywords: list[str]
    default_enabled: bool
    installed: bool
    runnable: bool


class SkillManifestView(BaseModel):
    """Full manifest view for ``get_skill_manifest``."""

    fqid: str
    pack_id: str
    skill_id: str
    version: str
    description: str
    required_servers: list[str]
    asset_types: list[str]
    keywords: list[str]
    default_enabled: bool
    installed: bool
    runnable: bool


class MarketplaceError(BaseModel):
    error: str


def repo_root() -> Path:
    """Repository root (directory containing ``src/``)."""
    # servers/skills/registry.py -> parents[3] == repo root
    return Path(__file__).resolve().parents[3]


def bundled_packs_root() -> Path:
    return Path(__file__).resolve().parent / "packs"


def _parse_extra_pack_dirs() -> list[Path]:
    raw = os.environ.get("SKILL_PACK_DIRS", "").strip()
    if not raw:
        return []
    return [Path(p.strip()).expanduser() for p in raw.split(",") if p.strip()]


def _manifest_path(pack_dir: Path) -> Path | None:
    y = pack_dir / "manifest.yaml"
    if y.is_file():
        return y
    y2 = pack_dir / "manifest.yml"
    if y2.is_file():
        return y2
    return None


def _load_pack_directory(pack_dir: Path) -> tuple[str, list[SkillPackRecord]]:
    manifest = _manifest_path(pack_dir)
    if manifest is None:
        return "", []
    with manifest.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise MarketplaceLoadError(f"invalid manifest root in {manifest}")
    pack_id = (data.get("pack_id") or "").strip()
    if not pack_id:
        raise MarketplaceLoadError(f"missing pack_id in {manifest}")
    if FQID_SEP in pack_id:
        raise MarketplaceLoadError(
            f"pack_id must not contain {FQID_SEP!r}: {pack_id!r}"
        )
    entries = data.get("skills")
    if not entries:
        return pack_id, []
    if not isinstance(entries, list):
        raise MarketplaceLoadError(f"skills must be a list in {manifest}")
    records = [SkillPackRecord.model_validate(item) for item in entries]
    for rec in records:
        if not rec.id.strip():
            raise MarketplaceLoadError(f"empty skill id in {manifest}")
        if FQID_SEP in rec.id:
            raise MarketplaceLoadError(
                f"skill id must not contain {FQID_SEP!r}: {rec.id!r}"
            )
    return pack_id, records


def merge_pack_records() -> tuple[SkillRecord, ...]:
    """Load all pack directories; duplicate FQID is a hard error."""
    seen: dict[str, Path] = {}
    out: list[SkillRecord] = []
    ordered_dirs: list[tuple[Path, Path]] = []

    bundled = bundled_packs_root()
    if bundled.is_dir():
        for sub in sorted(bundled.iterdir(), key=lambda p: p.name):
            if sub.is_dir() and _manifest_path(sub) is not None:
                ordered_dirs.append((sub, sub))

    for extra_root in _parse_extra_pack_dirs():
        if not extra_root.is_dir():
            raise MarketplaceLoadError(f"SKILL_PACK_DIRS entry is not a directory: {extra_root}")
        manifest = _manifest_path(extra_root)
        if manifest is not None:
            ordered_dirs.append((extra_root, extra_root))
            continue
        for sub in sorted(extra_root.iterdir(), key=lambda p: p.name):
            if sub.is_dir() and _manifest_path(sub) is not None:
                ordered_dirs.append((extra_root, sub))

    for _root, pack_dir in ordered_dirs:
        pack_id, rows = _load_pack_directory(pack_dir)
        if not rows:
            continue
        for row in rows:
            sid = row.id.strip()
            fqid = f"{pack_id}{FQID_SEP}{sid}"
            if fqid in seen:
                raise MarketplaceLoadError(
                    f"duplicate skill FQID {fqid!r} (first={seen[fqid]}, second={pack_dir})"
                )
            seen[fqid] = pack_dir
            out.append(
                SkillRecord(
                    fqid=fqid,
                    pack_id=pack_id,
                    skill_id=sid,
                    version=row.version,
                    description=row.description.strip(),
                    required_servers=list(row.required_servers),
                    asset_types=list(row.asset_types),
                    keywords=list(row.keywords),
                    default_enabled=row.default_enabled,
                )
            )
    return tuple(out)


def default_install_state_path() -> Path:
    custom = os.environ.get("SKILL_INSTALL_STATE_PATH", "").strip()
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".assetopsbench" / "skill_install_state.json"


def _normalize_install_list_entry(
    token: str,
    *,
    catalog: tuple[SkillRecord, ...],
    path: Path,
) -> str | None:
    """Return a catalog FQID or None if the token is unknown or ambiguous."""
    s = token.strip()
    if not s:
        return None
    known = {r.fqid for r in catalog}
    if FQID_SEP in s:
        if s in known:
            return s
        _log.warning("Ignoring unknown skill FQID %r in install state %s", s, path)
        return None
    matches = [r.fqid for r in catalog if r.skill_id == s]
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        _log.warning("Ignoring unknown bare skill id %r in install state %s", s, path)
        return None
    _log.warning(
        "Ignoring ambiguous bare skill id %r (matches %s) in install state %s",
        s,
        matches,
        path,
    )
    return None


def read_installed_fqids() -> frozenset[str]:
    path = default_install_state_path()
    if not path.is_file():
        return frozenset()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning(
            "Install state %s is unreadable (%s); treating as no skills installed",
            path,
            exc,
        )
        return frozenset()
    raw = data.get("installed")
    if not isinstance(raw, list):
        _log.warning(
            "Install state %s: key `installed` is not a list; treating as empty",
            path,
        )
        return frozenset()
    catalog = load_skill_catalog()
    out: set[str] = set()
    for x in raw:
        if not str(x).strip():
            continue
        resolved = _normalize_install_list_entry(
            str(x), catalog=catalog, path=path
        )
        if resolved:
            out.add(resolved)
    return frozenset(out)


def write_installed_fqids(fqids: frozenset[str]) -> None:
    path = default_install_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"installed": sorted(fqids)}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def maybe_bootstrap_install_state() -> None:
    """Create install state with all catalog FQIDs if missing (opt-in).

    When ``SKILL_BOOTSTRAP_INSTALL`` is truthy and the file at
    ``SKILL_INSTALL_STATE_PATH`` (or its default) does not exist yet, write an
    ``installed`` list containing every FQID from the merged catalog. Never
    overwrites an existing file.

    Call from ``skills-mcp-server`` :func:`main` so import-based tests do not
    trigger writes to the operator home directory.
    """
    if not _env_truthy("SKILL_BOOTSTRAP_INSTALL"):
        return
    path = default_install_state_path()
    if path.is_file():
        return
    catalog = load_skill_catalog()
    fqids = frozenset(r.fqid for r in catalog)
    if not fqids:
        return
    write_installed_fqids(fqids)
    logging.getLogger(__name__).info(
        "Skill install state created at %s (%d FQIDs); SKILL_BOOTSTRAP_INSTALL is set.",
        path,
        len(fqids),
    )


def _runnable(
    fqid: str,
    *,
    default_enabled: bool,
    installed: bool,
    env_allow: frozenset[str] | None,
) -> bool:
    if not default_enabled:
        return False
    if not installed:
        return False
    if env_allow is not None and fqid not in env_allow:
        return False
    return True


def clear_skill_catalog_cache() -> None:
    """Drop the in-memory catalog (for tests or after changing pack discovery inputs)."""
    global _catalog_cache
    _catalog_cache = None


def load_skill_catalog() -> tuple[SkillRecord, ...]:
    global _catalog_cache
    if _catalog_cache is None:
        _catalog_cache = merge_pack_records()
    return _catalog_cache


def coerce_skill_fqid(
    raw: str,
    catalog: tuple[SkillRecord, ...] | None = None,
) -> str:
    """Expand a short per-pack ``skill_id`` to a full FQID when unambiguous.

    Callers (including LLM-driven clients) sometimes pass ``safety_clearance_check``
    instead of ``assetopsbench_demo/safety_clearance_check``. If ``raw`` contains
    no ``/``, and exactly one catalog row has that ``skill_id``, return its ``fqid``.
    """
    s = raw.strip()
    if not s or FQID_SEP in s:
        return s
    cat = catalog if catalog is not None else load_skill_catalog()
    matches = [r.fqid for r in cat if r.skill_id == s]
    if len(matches) == 1:
        return matches[0]
    return s


def parse_enabled_skills_allowlist() -> frozenset[str] | None:
    """Comma-separated allowlist; each token is expanded via :func:`coerce_skill_fqid`.

    Legacy ``ENABLED_SKILLS=pump_seal_inspection`` thus matches
    ``assetopsbench/pump_seal_inspection``.
    """
    raw = os.environ.get("ENABLED_SKILLS", "").strip()
    if not raw:
        return None
    catalog = load_skill_catalog()
    known = {r.fqid for r in catalog}
    out: set[str] = set()
    for part in raw.split(","):
        t = part.strip()
        if not t:
            continue
        resolved = coerce_skill_fqid(t, catalog)
        if FQID_SEP not in resolved:
            _log.warning(
                "ENABLED_SKILLS token %r ignored (unknown or ambiguous bare skill id)",
                t,
            )
            continue
        if resolved not in known:
            _log.warning(
                "ENABLED_SKILLS token %r ignored (not a catalog FQID)",
                t,
            )
            continue
        out.add(resolved)
    return frozenset(out)


def list_skill_items() -> list[SkillListItem]:
    catalog = load_skill_catalog()
    installed = read_installed_fqids()
    env_allow = parse_enabled_skills_allowlist()
    items: list[SkillListItem] = []
    for rec in catalog:
        ins = rec.fqid in installed
        run = _runnable(
            rec.fqid,
            default_enabled=rec.default_enabled,
            installed=ins,
            env_allow=env_allow,
        )
        items.append(
            SkillListItem(
                fqid=rec.fqid,
                pack_id=rec.pack_id,
                skill_id=rec.skill_id,
                version=rec.version,
                description=rec.description,
                required_servers=list(rec.required_servers),
                asset_types=list(rec.asset_types),
                keywords=list(rec.keywords),
                default_enabled=rec.default_enabled,
                installed=ins,
                runnable=run,
            )
        )
    return items


def get_manifest_for_fqid(fqid: str) -> SkillManifestView | MarketplaceError:
    catalog = load_skill_catalog()
    target = coerce_skill_fqid(fqid.strip(), catalog)
    installed = read_installed_fqids()
    env_allow = parse_enabled_skills_allowlist()
    for rec in catalog:
        if rec.fqid != target:
            continue
        ins = rec.fqid in installed
        run = _runnable(
            rec.fqid,
            default_enabled=rec.default_enabled,
            installed=ins,
            env_allow=env_allow,
        )
        return SkillManifestView(
            fqid=rec.fqid,
            pack_id=rec.pack_id,
            skill_id=rec.skill_id,
            version=rec.version,
            description=rec.description,
            required_servers=list(rec.required_servers),
            asset_types=list(rec.asset_types),
            keywords=list(rec.keywords),
            default_enabled=rec.default_enabled,
            installed=ins,
            runnable=run,
        )
    return MarketplaceError(error=f"unknown skill fqid: {fqid!r} (use full id pack/skill or list_skills)")
