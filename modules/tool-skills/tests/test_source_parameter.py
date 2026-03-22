"""Tests for the load_skill source parameter feature."""

import pytest
from pathlib import Path
from amplifier_module_tool_skills import SkillsTool


def test_input_schema_includes_source():
    """Test that input_schema advertises the 'source' parameter."""
    tool = SkillsTool(config={})
    schema = tool.input_schema
    assert "source" in schema["properties"]
    assert schema["properties"]["source"]["type"] == "string"
    assert "description" in schema["properties"]["source"]


@pytest.mark.asyncio
async def test_resolve_source_local_path_exists(tmp_path):
    """Test _resolve_source returns path for existing local directory."""
    # Create a directory with a SKILL.md so it's a plausible skills dir
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: my-skill
description: Test skill
---
# Test""")

    tool = SkillsTool(config={})
    result = await tool._resolve_source(str(tmp_path))
    assert result is not None
    assert result == tmp_path.resolve()


@pytest.mark.asyncio
async def test_resolve_source_local_path_not_exists():
    """Test _resolve_source returns None for nonexistent path."""
    tool = SkillsTool(config={})
    result = await tool._resolve_source("/nonexistent/path/that/does/not/exist")
    assert result is None


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

    async def emit(self, event_name: str, data):
        self.emitted_events.append((event_name, data))
        if event_name in self.listeners:
            for listener in self.listeners[event_name]:
                await listener(event_name, data)


class MockMentionResolver:
    """Mock mention resolver capability."""

    def __init__(self, resolve_map: dict[str, Path]):
        self.resolve_map = resolve_map
        self.calls = []

    def resolve(self, mention: str) -> Path | None:
        self.calls.append(mention)
        return self.resolve_map.get(mention)


@pytest.mark.asyncio
async def test_resolve_source_mention_with_resolver(tmp_path):
    """Test _resolve_source resolves @namespace:path via mention_resolver."""
    resolver = MockMentionResolver({"@superpowers:skills": tmp_path})
    coordinator = MockCoordinator()
    coordinator.register_capability("mention_resolver", resolver)

    tool = SkillsTool(config={}, coordinator=coordinator)
    result = await tool._resolve_source("@superpowers:skills")

    assert result == tmp_path
    assert resolver.calls == ["@superpowers:skills"]


@pytest.mark.asyncio
async def test_resolve_source_mention_no_resolver():
    """Test _resolve_source returns None when mention_resolver not available."""
    coordinator = MockCoordinator()
    # No mention_resolver registered

    tool = SkillsTool(config={}, coordinator=coordinator)
    result = await tool._resolve_source("@nonexistent:bundle")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_source_remote_url(tmp_path, monkeypatch):
    """Test _resolve_source resolves git+https:// via resolve_skill_source."""
    expected_path = tmp_path / "cached-skills"
    expected_path.mkdir()

    async def mock_resolve(source, cache_dir=None):
        return expected_path

    monkeypatch.setattr(
        "amplifier_module_tool_skills.resolve_skill_source",
        mock_resolve,
    )

    tool = SkillsTool(config={})
    result = await tool._resolve_source("git+https://github.com/example/skills@main")

    assert result == expected_path


@pytest.mark.asyncio
async def test_resolve_source_remote_url_fails(monkeypatch):
    """Test _resolve_source returns None when remote resolution fails."""

    async def mock_resolve(source, cache_dir=None):
        return None

    monkeypatch.setattr(
        "amplifier_module_tool_skills.resolve_skill_source",
        mock_resolve,
    )

    tool = SkillsTool(config={})
    result = await tool._resolve_source("git+https://github.com/nonexistent/repo@main")

    assert result is None


@pytest.mark.asyncio
async def test_execute_source_discovers_and_merges_skills(tmp_path):
    """Test execute with source param discovers skills and merges them."""
    # Create a source directory with skills
    skill_dir = tmp_path / "new-source" / "cool-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("""---
name: cool-skill
description: A cool new skill
---
# Cool Skill Content""")

    coordinator = MockCoordinator()
    tool = SkillsTool(config={}, coordinator=coordinator)

    # Verify skill doesn't exist yet
    assert "cool-skill" not in tool.skills

    result = await tool.execute({"source": str(tmp_path / "new-source")})

    assert result.success is True
    assert "cool-skill" in tool.skills
    assert "cool-skill" in str(result.output)


# --- Task 6: Deduplication — existing skills take priority ---


@pytest.mark.asyncio
async def test_execute_source_existing_skills_take_priority(tmp_path):
    """Test that existing skills are NOT overwritten by source skills."""
    # Create mount-time skills directory with python-standards
    mount_dir = tmp_path / "mount-skills" / "python-standards"
    mount_dir.mkdir(parents=True)
    (mount_dir / "SKILL.md").write_text("""---
name: python-standards
description: Original mount-time skill
---
# Original Content""")

    # Create source directory with a DIFFERENT python-standards
    source_dir = tmp_path / "source-skills" / "python-standards"
    source_dir.mkdir(parents=True)
    (source_dir / "SKILL.md").write_text("""---
name: python-standards
description: Overriding source skill
---
# Overriding Content""")

    coordinator = MockCoordinator()
    tool = SkillsTool(
        config={},
        coordinator=coordinator,
        resolved_dirs=[tmp_path / "mount-skills"],
    )

    # Verify original is loaded
    assert tool.skills["python-standards"].description == "Original mount-time skill"

    result = await tool.execute({"source": str(tmp_path / "source-skills")})

    assert result.success is True
    # Original skill must still be there, NOT overwritten
    assert tool.skills["python-standards"].description == "Original mount-time skill"


# --- Task 7: Error handling ---


@pytest.mark.asyncio
async def test_execute_source_nonexistent_path():
    """Test execute with nonexistent source path returns clear error."""
    coordinator = MockCoordinator()
    tool = SkillsTool(config={}, coordinator=coordinator)

    result = await tool.execute({"source": "/nonexistent/path/nowhere"})

    assert result.success is False
    assert "Could not resolve source" in str(result.output)
    assert "/nonexistent/path/nowhere" in str(result.output)


@pytest.mark.asyncio
async def test_execute_source_empty_directory(tmp_path):
    """Test execute with source dir containing no skills returns success with 0 count."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    coordinator = MockCoordinator()
    tool = SkillsTool(config={}, coordinator=coordinator)

    result = await tool.execute({"source": str(empty_dir)})

    assert result.success is True
    assert "0 skill(s)" in str(result.output)


@pytest.mark.asyncio
async def test_execute_source_mention_no_resolver():
    """Test execute with @mention when no mention_resolver is available."""
    coordinator = MockCoordinator()
    # No mention_resolver capability registered
    tool = SkillsTool(config={}, coordinator=coordinator)

    result = await tool.execute({"source": "@nonexistent:namespace"})

    assert result.success is False
    assert "Could not resolve source" in str(result.output)


# --- Task 8: Parameter combination — source + skill_name ---


@pytest.mark.asyncio
async def test_execute_source_plus_skill_name(tmp_path):
    """Test source + skill_name: registers source then loads the skill."""
    # Create source with a skill
    skill_dir = tmp_path / "ext-skills" / "fancy-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("""---
name: fancy-skill
description: A fancy skill
---
# Fancy Skill

This is the full content of the fancy skill.""")

    coordinator = MockCoordinator()
    tool = SkillsTool(config={}, coordinator=coordinator)

    result = await tool.execute(
        {
            "source": str(tmp_path / "ext-skills"),
            "skill_name": "fancy-skill",
        }
    )

    assert result.success is True
    # Should return the skill CONTENT, not just the discovery summary
    output = result.output
    assert "fancy-skill" in str(output)
    assert "Fancy Skill" in str(output)
    assert "full content" in str(output)


# --- Task 9: Parameter combination — source + list ---


@pytest.mark.asyncio
async def test_execute_source_plus_list(tmp_path):
    """Test source + list=True: registers source then lists all skills."""
    # Create mount-time skills
    mount_dir = tmp_path / "mount-skills" / "existing-skill"
    mount_dir.mkdir(parents=True)
    (mount_dir / "SKILL.md").write_text("""---
name: existing-skill
description: Already mounted skill
---
# Existing""")

    # Create source skills
    source_dir = tmp_path / "source-skills" / "new-skill"
    source_dir.mkdir(parents=True)
    (source_dir / "SKILL.md").write_text("""---
name: new-skill
description: Newly added skill
---
# New""")

    coordinator = MockCoordinator()
    tool = SkillsTool(
        config={},
        coordinator=coordinator,
        resolved_dirs=[tmp_path / "mount-skills"],
    )

    result = await tool.execute(
        {
            "source": str(tmp_path / "source-skills"),
            "list": True,
        }
    )

    assert result.success is True
    output_str = str(result.output)
    # Should list BOTH existing and new skills
    assert "existing-skill" in output_str
    assert "new-skill" in output_str


# --- Task 10: Visibility hook auto-update verification ---


@pytest.mark.asyncio
async def test_visibility_hook_sees_source_skills(tmp_path):
    """Test that visibility hook auto-updates when source adds skills.

    The SkillsVisibilityHook holds a DIRECT reference to tool.skills (not a copy).
    Mutating tool.skills via execute(source=...) should automatically propagate.
    """
    from amplifier_module_tool_skills.hooks import SkillsVisibilityHook

    # Create mount-time skill
    mount_dir = tmp_path / "mount-skills" / "original-skill"
    mount_dir.mkdir(parents=True)
    (mount_dir / "SKILL.md").write_text("""---
name: original-skill
description: Original skill
---
# Original""")

    coordinator = MockCoordinator()
    tool = SkillsTool(
        config={},
        coordinator=coordinator,
        resolved_dirs=[tmp_path / "mount-skills"],
    )

    # Create visibility hook with reference to tool.skills (same as mount() does)
    hook = SkillsVisibilityHook(tool.skills, {"enabled": True})

    # Verify hook only sees original skill
    result = await hook.on_provider_request("provider:request", {})
    assert "original-skill" in result.context_injection
    assert "added-skill" not in result.context_injection

    # Now add a source with a new skill
    source_dir = tmp_path / "source-skills" / "added-skill"
    source_dir.mkdir(parents=True)
    (source_dir / "SKILL.md").write_text("""---
name: added-skill
description: Dynamically added skill
---
# Added""")

    await tool.execute({"source": str(tmp_path / "source-skills")})

    # Hook should NOW see the new skill (same dict reference)
    result = await hook.on_provider_request("provider:request", {})
    assert "original-skill" in result.context_injection
    assert "added-skill" in result.context_injection


# --- Task 11: Verify skills:discovered event emission ---


@pytest.mark.asyncio
async def test_execute_source_emits_discovered_event(tmp_path):
    """Test that execute with source emits skills:discovered event."""
    skill_dir = tmp_path / "event-skills" / "event-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("""---
name: event-skill
description: Skill for event testing
---
# Event Test""")

    coordinator = MockCoordinator()
    tool = SkillsTool(config={}, coordinator=coordinator)

    await tool.execute({"source": str(tmp_path / "event-skills")})

    # Find the skills:discovered event
    discovered_events = [
        (name, data)
        for name, data in coordinator.hooks.emitted_events
        if name == "skills:discovered"
    ]
    assert len(discovered_events) == 1

    event_name, data = discovered_events[0]
    assert data["skill_count"] == 1
    assert "event-skill" in data["skill_names"]
    assert len(data["sources"]) == 1
