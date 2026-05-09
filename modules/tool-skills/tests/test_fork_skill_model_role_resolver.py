"""Regression test for fork-skill model_role resolution.

This file documents and locks down the fix for a pre-existing bug where fork
skills declaring ``model_role`` silently fell back to the parent's default
provider, regardless of which routing matrix was active.

Root cause:
    SkillsTool._execute_fork() looked up a capability named ``"routing_matrix"``
    that was never registered (the routing-matrix bundle wrote
    ``session_state["routing_matrix"]`` instead). The lookup returned ``None``,
    the resolution branch was skipped, and ``provider_preferences=None``
    was passed to ``spawn_fn`` \u2014 so the child session inherited the parent's
    priority-1 provider regardless of the active matrix.

Fix (this PR):
    Renamed and reshaped the capability to ``model_role_resolver`` (a generic
    duck-typed contract usable by any routing strategy). Tool-skills now
    awaits ``resolver.resolve(role)`` and forwards the resulting
    ``list[ProviderPreference]`` to ``spawn_fn``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amplifier_foundation.spawn_utils import ProviderPreference
from amplifier_module_tool_skills import SkillsTool
from amplifier_module_tool_skills.discovery import SkillMetadata


def _make_fork_metadata(*, model_role: str = "research", tmp_path: Path | None = None):
    """Build a SkillMetadata describing a fork-context skill with model_role."""
    if tmp_path is None:
        tmp_path = Path("/tmp/_test_skill")
    skill_dir = tmp_path / "research-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text("# stub\n", encoding="utf-8")
    return SkillMetadata(
        name="research-skill",
        description="Test fork skill that declares a model_role",
        path=skill_path,
        source=str(tmp_path),
        context="fork",
        model_role=model_role,
        # No explicit provider_preferences \u2014 should be resolved via the
        # model_role_resolver capability.
        provider_preferences=None,
    )


def _make_coordinator_with_resolver(resolver=None, spawn_fn=None) -> MagicMock:
    """Build a coordinator mock with a model_role_resolver capability."""
    coordinator = MagicMock()
    coordinator.session = MagicMock()
    coordinator.config = {"agents": {}}
    coordinator.hooks = MagicMock()
    coordinator.hooks.emit = AsyncMock()

    capabilities: dict = {
        "model_role_resolver": resolver,
        "session.spawn": spawn_fn or AsyncMock(
            return_value={
                "output": "child-output",
                "session_id": "child-123",
                "status": "success",
                "turn_count": 1,
                "metadata": {},
            }
        ),
    }
    coordinator.get_capability = MagicMock(side_effect=capabilities.get)
    return coordinator


@pytest.mark.asyncio
async def test_fork_skill_with_model_role_consults_resolver_capability(tmp_path):
    """Fork skills declaring model_role MUST consult model_role_resolver capability.

    Pre-fix behavior: the resolver was looked up under the wrong capability
    name (``routing_matrix``), found nothing, and silently passed
    provider_preferences=None to spawn_fn. This test fails pre-fix because
    ``resolver.resolve`` is never called.
    """
    # The resolver returns a deterministic preference for role "research".
    resolver = MagicMock()
    resolver.name = "test-matrix"
    resolver.resolve = AsyncMock(
        return_value=[
            ProviderPreference(provider="openai", model="gpt-test"),
        ]
    )

    spawn_fn = AsyncMock(
        return_value={
            "output": "child-output",
            "session_id": "child-123",
            "status": "success",
            "turn_count": 1,
            "metadata": {},
        }
    )
    coordinator = _make_coordinator_with_resolver(resolver=resolver, spawn_fn=spawn_fn)

    tool = SkillsTool(config={}, coordinator=coordinator, resolved_dirs=[])
    metadata = _make_fork_metadata(model_role="research", tmp_path=tmp_path)

    # Bypass body preprocessing \u2014 not under test here.
    with patch(
        "amplifier_module_tool_skills.preprocess",
        new=AsyncMock(return_value="processed body"),
    ):
        result = await tool._execute_fork("research-skill", metadata, "raw body")

    # Resolver MUST have been consulted exactly once with the declared role.
    resolver.resolve.assert_awaited_once_with("research")

    # spawn_fn MUST have received the resolved provider preferences.
    spawn_fn.assert_awaited_once()
    _, kwargs = spawn_fn.call_args
    prefs = kwargs.get("provider_preferences")
    assert prefs is not None, (
        "Expected provider_preferences from model_role_resolver, got None \u2014 "
        "fork-skill bug regression: capability lookup or resolver call broken"
    )
    assert len(prefs) == 1
    assert prefs[0].provider == "openai"
    assert prefs[0].model == "gpt-test"

    # And the call succeeded.
    assert result.success is True


@pytest.mark.asyncio
async def test_fork_skill_with_model_role_falls_through_when_no_resolver(tmp_path):
    """When no model_role_resolver capability is registered, fall through gracefully.

    The fork should still spawn (with provider_preferences=None, which means
    the child inherits the parent's default provider). This tests fail-forward
    semantics: a missing routing bundle is not a hard error.
    """
    spawn_fn = AsyncMock(
        return_value={
            "output": "child-output",
            "session_id": "child-123",
            "status": "success",
            "turn_count": 1,
            "metadata": {},
        }
    )
    coordinator = _make_coordinator_with_resolver(resolver=None, spawn_fn=spawn_fn)

    tool = SkillsTool(config={}, coordinator=coordinator, resolved_dirs=[])
    metadata = _make_fork_metadata(model_role="research", tmp_path=tmp_path)

    with patch(
        "amplifier_module_tool_skills.preprocess",
        new=AsyncMock(return_value="processed body"),
    ):
        result = await tool._execute_fork("research-skill", metadata, "raw body")

    spawn_fn.assert_awaited_once()
    _, kwargs = spawn_fn.call_args
    assert kwargs.get("provider_preferences") is None
    assert result.success is True
