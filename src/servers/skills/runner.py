"""Dispatch ``run_skill`` to handlers after catalog + runnability checks."""

from __future__ import annotations

from pydantic import ValidationError

from .handlers import HANDLERS
from .registry import MarketplaceError, get_manifest_for_fqid
from .results import SkillInvocationError, SkillRunResult
from .sibling_mcp import close_sibling_pool, get_sibling_pool


async def run_skill_impl(
    skill_id: str,
    arguments: dict,
) -> SkillRunResult | SkillInvocationError:
    try:
        manifest = get_manifest_for_fqid(skill_id.strip())
        if isinstance(manifest, MarketplaceError):
            return SkillInvocationError(error=manifest.error)
        fqid = manifest.fqid
        if not manifest.runnable:
            if not manifest.installed:
                return SkillInvocationError(
                    error=(
                        "skill is not installed: add this FQID to `installed` in "
                        "SKILL_INSTALL_STATE_PATH (see servers/skills/examples/install_state.example.json), "
                        "or set SKILL_BOOTSTRAP_INSTALL=1 and restart skills-mcp-server once to auto-create the file."
                    )
                )
            if not manifest.default_enabled:
                return SkillInvocationError(
                    error="skill is disabled in the pack manifest (default_enabled=false)"
                )
            return SkillInvocationError(
                error=(
                    f"skill is blocked by ENABLED_SKILLS: add {fqid!r} to that env var "
                    "(comma-separated; bare skill suffixes are expanded to full FQIDs when unambiguous), "
                    "or clear ENABLED_SKILLS to disable the allowlist."
                )
            )
        handler = HANDLERS.get(fqid)
        if handler is None:
            return SkillInvocationError(
                error=f"no handler registered for {fqid!r} (marketplace/catalog mismatch)"
            )
        pool = get_sibling_pool()
        try:
            result = await handler(pool, arguments)
            if not isinstance(result, SkillRunResult):
                return SkillInvocationError(error="handler returned unexpected type")
            return result
        except ValidationError as exc:
            return SkillInvocationError(error=f"invalid arguments: {exc}")
        except Exception as exc:
            return SkillInvocationError(error=f"skill execution failed: {exc}")
    finally:
        # Close sibling stdio sessions before the parent drops our stdin (avoids AnyIO
        # cancel-scope teardown noise and stray output on shutdown).
        await close_sibling_pool()
