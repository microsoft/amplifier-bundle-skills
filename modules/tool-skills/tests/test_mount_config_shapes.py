"""Regression tests for tool-skills mount() fork-session detection.

Two contract guarantees covered here:

1. **Orchestrator-shape robustness.** `coordinator.config["session"]["orchestrator"]`
   can legitimately be either a plain string (common production case, e.g.
   ``"loop-basic"``) or a dict (when the spawner passes orchestrator_config for
   something like rate limiting). `mount()` must not assume either shape. This
   guards against regression of the clean-install crash that manifested as
   ``'str' object has no attribute 'get'`` during protocol_compliance
   validation before commit 0f00d19.

2. **Fork-session detection via session.metadata.** The parent's
   ``_execute_fork`` writes ``is_forked_skill_session: True`` into
   ``session_metadata``, which ``spawn_sub_session`` propagates verbatim into
   the child's ``config["session"]["metadata"]``. ``mount()`` must read the
   marker from there (not from ``orchestrator_config`` — that was the old path,
   and it was a semantic lie). Capabilities do NOT cross the spawn boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from amplifier_module_tool_skills import mount


class _MockHooks:
    def __init__(self) -> None:
        self.registered: list[dict[str, Any]] = []
        self.emitted: list[tuple[str, dict[str, Any]]] = []

    def register(
        self,
        event: str,
        handler: Callable,
        priority: int = 10,
        name: str | None = None,
    ) -> Callable | None:
        self.registered.append(
            {"event": event, "handler": handler, "priority": priority, "name": name}
        )
        return None

    async def emit(self, event_name: str, data: dict[str, Any]) -> None:
        self.emitted.append((event_name, data))


class _MockCoordinator:
    """Minimal coordinator that lets us vary config shapes test-by-test."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.capabilities: dict[str, Any] = {}
        self.mounted_tools: dict[str, Any] = {}
        self.hooks = _MockHooks()
        self.config: dict[str, Any] = config if config is not None else {}

    def register_capability(self, name: str, value: Any) -> None:
        self.capabilities[name] = value

    def get_capability(self, name: str) -> Any:
        return self.capabilities.get(name)

    async def mount(self, category: str, tool: Any, name: str) -> None:
        self.mounted_tools[name] = tool


# ---------------------------------------------------------------------------
# Orchestrator-shape robustness (independent of fork-session state)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mount_survives_string_orchestrator(tmp_path):
    """session.orchestrator stored as a plain string (MockCoordinator / production
    default) must not crash mount(). This is the clean-install scenario.
    """
    coordinator = _MockCoordinator(
        config={"session": {"orchestrator": "loop-basic", "context": "context-simple"}}
    )

    cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})

    assert cleanup is not None
    assert coordinator.get_capability("skills.fork_context") is None


@pytest.mark.asyncio
async def test_mount_survives_dict_orchestrator_without_fork_flag(tmp_path):
    """session.orchestrator as a dict is also valid (spawner may pass
    orchestrator_config for rate limiting etc.). A dict without a fork marker
    must be treated as a non-forked session.
    """
    coordinator = _MockCoordinator(
        config={
            "session": {
                "orchestrator": {"module": "loop-basic", "config": {}},
            }
        }
    )

    cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})
    assert cleanup is not None
    assert coordinator.get_capability("skills.fork_context") is None


@pytest.mark.asyncio
async def test_mount_survives_empty_config(tmp_path):
    """mount() with a coordinator that has no session config at all must not crash."""
    coordinator = _MockCoordinator(config={})

    cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})
    assert cleanup is not None
    assert coordinator.get_capability("skills.fork_context") is None


# ---------------------------------------------------------------------------
# Fork-session detection via session.metadata (single source of truth)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mount_detects_fork_marker_in_session_metadata(tmp_path):
    """When the parent's _execute_fork writes the marker into session_metadata
    and spawn_sub_session propagates it into the child's
    config["session"]["metadata"], mount() must detect it and register the
    skills.fork_context capability.
    """
    coordinator = _MockCoordinator(
        config={
            "session": {
                "orchestrator": "loop-basic",
                "metadata": {
                    "skill_name": "some-fork-skill",
                    "context": "fork",
                    "is_forked_skill_session": True,
                },
            }
        }
    )

    cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})
    assert cleanup is not None
    assert coordinator.get_capability("skills.fork_context") is True


@pytest.mark.asyncio
async def test_mount_ignores_orchestrator_config_marker(tmp_path):
    """The OLD propagation path (orchestrator_config.config._is_forked_skill_session)
    is intentionally no longer consulted. A coordinator whose config still has
    the old-shape marker but NO session.metadata marker must be treated as
    NOT forked. This pins the deprecation: if someone re-introduces the old
    read path, this test fails.
    """
    coordinator = _MockCoordinator(
        config={
            "session": {
                "orchestrator": {
                    "module": "loop-basic",
                    "config": {"_is_forked_skill_session": True},
                },
                # Note: no "metadata" key here
            }
        }
    )

    cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})
    assert cleanup is not None
    # NOT forked — the old orchestrator_config path is no longer read.
    assert coordinator.get_capability("skills.fork_context") is None


@pytest.mark.asyncio
async def test_mount_handles_non_dict_session_metadata(tmp_path):
    """session.metadata is expected to be a dict, but user-supplied TOML can
    put anything there. The isinstance guard in _detect_fork_session must
    short-circuit a string/list/None/etc. metadata value cleanly.
    """
    coordinator = _MockCoordinator(
        config={"session": {"orchestrator": "loop-basic", "metadata": "garbage"}}
    )

    cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})
    assert cleanup is not None
    assert coordinator.get_capability("skills.fork_context") is None


@pytest.mark.asyncio
async def test_mount_detects_fork_via_preregistered_capability(tmp_path):
    """The in-session capability path: if a sibling module or test harness
    has already registered skills.fork_context, mount() honours it even if
    no metadata marker is present.
    """
    coordinator = _MockCoordinator(config={"session": {"orchestrator": "loop-basic"}})
    coordinator.register_capability("skills.fork_context", True)

    cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})
    assert cleanup is not None
    # Still registered (idempotent).
    assert coordinator.get_capability("skills.fork_context") is True
