"""Regression tests for tool-skills mount() handling of varied orchestrator shapes.

coordinator.config["session"]["orchestrator"] is legitimately either a plain
string (common production case, e.g. "loop-basic") or a dict (when the spawner
passes orchestrator_config during a skill-fork session). The mount() code that
detects forked-skill sessions must handle both shapes without crashing.

This protects against regression of the crash introduced by commit 408131a,
where the dict-chain `.get("orchestrator", {}).get("config", {})` exploded with
`'str' object has no attribute 'get'` whenever the MockCoordinator validator
shape (string orchestrator) was exercised. The Amplifier core loader calls
mount() through its protocol_compliance check with exactly that MockCoordinator,
so this crash manifested as a hard module-load failure on every clean install.
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


@pytest.mark.asyncio
async def test_mount_survives_string_orchestrator(tmp_path):
    """session.orchestrator stored as a plain string (MockCoordinator / production default)
    must not crash the fork-detection fallback in mount().

    Regression test for the crash that appeared as:
        'str' object has no attribute 'get'
    during protocol_compliance validation on a clean install.
    """
    coordinator = _MockCoordinator(
        config={"session": {"orchestrator": "loop-basic", "context": "context-simple"}}
    )

    # Use an empty skills_dir so discovery is a no-op — we only care that mount() completes.
    cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})

    # mount() returned a cleanup callable (tuple or callable) — not a crash.
    assert cleanup is not None
    # And the fork-context capability was NOT registered (string orchestrator ⇒ not forked).
    assert coordinator.get_capability("skills.fork_context") is None


@pytest.mark.asyncio
async def test_mount_survives_dict_orchestrator_without_fork_flag(tmp_path):
    """session.orchestrator as a dict without _is_forked_skill_session must be treated
    as a non-forked session (clean pass-through of the fork guard)."""
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
async def test_mount_detects_fork_flag_via_config_dict(tmp_path):
    """When the spawner writes _is_forked_skill_session into
    session.orchestrator.config, mount() must detect it via the fallback path
    and register the skills.fork_context capability."""
    coordinator = _MockCoordinator(
        config={
            "session": {
                "orchestrator": {
                    "module": "loop-basic",
                    "config": {"_is_forked_skill_session": True},
                },
            }
        }
    )

    cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})
    assert cleanup is not None
    # The fallback path correctly detected the fork flag.
    assert coordinator.get_capability("skills.fork_context") is True


@pytest.mark.asyncio
async def test_mount_survives_empty_config(tmp_path):
    """mount() with a coordinator that has no session config at all must not crash."""
    coordinator = _MockCoordinator(config={})

    cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})
    assert cleanup is not None
    assert coordinator.get_capability("skills.fork_context") is None
