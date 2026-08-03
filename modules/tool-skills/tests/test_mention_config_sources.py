"""Tests for @namespace:path skill sources in config.skills (mount-time).

The docs (context/skills-instructions.md) promise that config.skills accepts
a bundle reference like "@mybundle:skills". Pre-fix, _resolve_skill_sources
only handled git+ URLs and literal paths: an @-entry fell into the
local-path branch, failed Path.exists(), and was silently dropped.

The fix defers @-sources to a one-shot resolution at the first
provider:request, because the mention_resolver capability is registered by
the app layer AFTER modules mount in every production session path.
"""

import logging
from pathlib import Path

import pytest

from amplifier_module_tool_skills import mount


class MockCoordinator:
    """Mock coordinator for testing."""

    def __init__(self):
        self.capabilities = {}
        self.mounted_tools = {}
        self.hooks = MockHooks()
        self.config = {}

    def register_capability(self, name: str, value):
        self.capabilities[name] = value

    def get_capability(self, name: str):
        return self.capabilities.get(name)

    def get(self, name: str):
        return None

    async def mount(self, category: str, tool, name: str):
        self.mounted_tools[name] = tool


class MockHooks:
    """Mock hooks system for testing."""

    def __init__(self):
        self.listeners = {}
        self.emitted_events = []
        self.registered_hooks = []

    def on(self, event_name: str, listener):
        if event_name not in self.listeners:
            self.listeners[event_name] = []
        self.listeners[event_name].append(listener)

    def register(self, event: str, handler, priority: int = 10, name: str = None):
        self.registered_hooks.append(
            {
                "event": event,
                "handler": handler,
                "priority": priority,
                "name": name,
            }
        )
        self.on(event, handler)

        def unregister():
            if handler in self.listeners.get(event, []):
                self.listeners[event].remove(handler)

        return unregister

    async def emit(self, event_name: str, data):
        self.emitted_events.append((event_name, data))
        # Copy: handlers may unregister themselves mid-iteration (one-shot hook)
        for listener in list(self.listeners.get(event_name, [])):
            await listener(event_name, data)


class MockMentionResolver:
    """Mock mention resolver capability."""

    def __init__(self, resolve_map: dict[str, Path]):
        self.resolve_map = resolve_map
        self.calls = []

    def resolve(self, mention: str) -> Path | None:
        self.calls.append(mention)
        return self.resolve_map.get(mention)


def _make_skill(base: Path, name: str, description: str) -> Path:
    """Create a skills dir containing one skill; return the skills dir."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"""---
name: {name}
description: {description}
---
# {name}
"""
    )
    return base


@pytest.mark.asyncio
async def test_mention_source_resolves_at_first_provider_request(tmp_path):
    """@-source skills merge at first provider:request; local sources unaffected."""
    bundle_skills = _make_skill(
        tmp_path / "bundle-skills", "bundle-skill", "Skill shipped inside a bundle"
    )
    local_skills = _make_skill(
        tmp_path / "local-skills", "local-skill", "Skill from a local path"
    )

    coordinator = MockCoordinator()
    await mount(
        coordinator,
        config={"skills": ["@mybundle:skills", str(local_skills)]},
    )
    tool = coordinator.mounted_tools["load_skill"]

    # Local source resolved at mount; @-source deferred (resolver not yet registered)
    assert "local-skill" in tool.skills
    assert "bundle-skill" not in tool.skills
    assert tool._pending_mention_sources == ["@mybundle:skills"]

    # The dedicated one-shot hook is registered on provider:request
    hook_names = [h["name"] for h in coordinator.hooks.registered_hooks]
    assert "skills-mention-sources" in hook_names

    # App layer registers the resolver AFTER mount (production order)
    resolver = MockMentionResolver({"@mybundle:skills": bundle_skills})
    coordinator.register_capability("mention_resolver", resolver)

    # First provider:request triggers one-shot resolution
    await coordinator.hooks.emit("provider:request", {})

    assert "bundle-skill" in tool.skills
    assert "local-skill" in tool.skills
    assert bundle_skills in tool.skills_dirs
    assert tool._pending_mention_sources == []
    assert resolver.calls == ["@mybundle:skills"]

    # One-shot: a second request does not re-resolve
    await coordinator.hooks.emit("provider:request", {})
    assert resolver.calls == ["@mybundle:skills"]


@pytest.mark.asyncio
async def test_mention_source_propagates_to_visibility_and_discovery(tmp_path):
    """In-place merge propagates to SkillsVisibilityHook and SkillsDiscovery."""
    bundle_skills = _make_skill(
        tmp_path / "bundle-skills", "bundle-skill", "Skill shipped inside a bundle"
    )

    coordinator = MockCoordinator()
    await mount(coordinator, config={"skills": ["@mybundle:skills"]})

    discovery = coordinator.get_capability("skills_discovery")
    assert discovery.find("bundle-skill") is None

    coordinator.register_capability(
        "mention_resolver", MockMentionResolver({"@mybundle:skills": bundle_skills})
    )
    await coordinator.hooks.emit("provider:request", {})

    # SkillsDiscovery holds a reference to the same dict — sees the merge
    assert discovery.find("bundle-skill") is not None
    # Visibility hook renders from the same catalog
    visibility = [
        h
        for h in coordinator.hooks.registered_hooks
        if h["name"] == "skills-visibility"
    ]
    assert len(visibility) == 1
    result = await visibility[0]["handler"]("provider:request", {})
    assert "bundle-skill" in (result.context_injection or "")

    # A skills:discovered event was emitted for the merged source
    discovered = [
        data
        for name, data in coordinator.hooks.emitted_events
        if name == "skills:discovered" and "bundle-skill" in data["skill_names"]
    ]
    assert len(discovered) == 1


@pytest.mark.asyncio
async def test_mention_source_warns_when_resolver_never_appears(tmp_path, caplog):
    """If no mention_resolver ever registers, dropped sources are named LOUDLY."""
    local_skills = _make_skill(
        tmp_path / "local-skills", "local-skill", "Skill from a local path"
    )

    coordinator = MockCoordinator()
    await mount(
        coordinator,
        config={"skills": ["@mybundle:skills", str(local_skills)]},
    )
    tool = coordinator.mounted_tools["load_skill"]

    with caplog.at_level(logging.WARNING, logger="amplifier_module_tool_skills"):
        await coordinator.hooks.emit("provider:request", {})

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("@mybundle:skills" in r.getMessage() for r in warnings), (
        "Dropped @-source must be named in a WARNING"
    )
    assert any("mention_resolver" in r.getMessage() for r in warnings)

    # Other sources unaffected
    assert "local-skill" in tool.skills
    assert tool._pending_mention_sources == []


@pytest.mark.asyncio
async def test_mention_source_warns_when_resolution_fails(tmp_path, caplog):
    """Resolver present but returns None -> WARNING naming the source."""
    coordinator = MockCoordinator()
    await mount(coordinator, config={"skills": ["@mybundle:skills"]})
    tool = coordinator.mounted_tools["load_skill"]

    coordinator.register_capability("mention_resolver", MockMentionResolver({}))

    with caplog.at_level(logging.WARNING, logger="amplifier_module_tool_skills"):
        await coordinator.hooks.emit("provider:request", {})

    assert any(
        "@mybundle:skills" in r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.WARNING
    )
    assert "bundle-skill" not in tool.skills


@pytest.mark.asyncio
async def test_mention_source_resolves_eagerly_when_resolver_present_at_mount(
    tmp_path,
):
    """Future-proofing: if mention_resolver exists at mount, resolve immediately."""
    bundle_skills = _make_skill(
        tmp_path / "bundle-skills", "bundle-skill", "Skill shipped inside a bundle"
    )

    coordinator = MockCoordinator()
    coordinator.register_capability(
        "mention_resolver", MockMentionResolver({"@mybundle:skills": bundle_skills})
    )
    await mount(coordinator, config={"skills": ["@mybundle:skills"]})
    tool = coordinator.mounted_tools["load_skill"]

    # Skills present from mount; nothing deferred, no one-shot hook registered
    assert "bundle-skill" in tool.skills
    assert tool._pending_mention_sources == []
    hook_names = [h["name"] for h in coordinator.hooks.registered_hooks]
    assert "skills-mention-sources" not in hook_names


@pytest.mark.asyncio
async def test_pure_local_config_unchanged(tmp_path):
    """Regression: configs without @-sources behave exactly as before."""
    local_skills = _make_skill(
        tmp_path / "local-skills", "local-skill", "Skill from a local path"
    )

    coordinator = MockCoordinator()
    await mount(coordinator, config={"skills": [str(local_skills)]})
    tool = coordinator.mounted_tools["load_skill"]

    assert "local-skill" in tool.skills
    assert tool._pending_mention_sources == []
    hook_names = [h["name"] for h in coordinator.hooks.registered_hooks]
    assert "skills-mention-sources" not in hook_names


@pytest.mark.asyncio
async def test_mention_only_config_does_not_fall_back_to_defaults(tmp_path):
    """A config that lists ONLY @-sources counts as 'sources configured'.

    Pre-fix, the dropped @-source made the config look empty and the tool
    fell back to default skill directories. Post-fix, the pending source
    suppresses the defaults fallback: the session gets exactly the skills
    the bundle asked for (at first request), not accidental defaults.
    """
    coordinator = MockCoordinator()
    await mount(coordinator, config={"skills": ["@mybundle:skills"]})
    tool = coordinator.mounted_tools["load_skill"]

    assert tool.skills_dirs == []
    assert tool._pending_mention_sources == ["@mybundle:skills"]
