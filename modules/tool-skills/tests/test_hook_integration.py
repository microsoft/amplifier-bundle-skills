"""Integration tests for skills visibility hook."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from amplifier_module_tool_skills import mount
from amplifier_module_tool_skills.hooks import SkillsVisibilityHook


class MockCoordinator:
    """Mock coordinator that processes hook results."""

    def __init__(self):
        self.capabilities = {}
        self.mounted_tools = {}
        self.hooks = MockHooks()
        self.config = {}

    def register_capability(self, name: str, value):
        self.capabilities[name] = value

    def get_capability(self, name: str):
        return self.capabilities.get(name)

    async def mount(self, category: str, tool, name: str):
        self.mounted_tools[name] = tool


class MockHooks:
    """Mock hooks system that tracks registrations."""

    def __init__(self):
        self.registered_hooks = []
        self.emitted_events = []

    def register(
        self, event: str, handler, priority: int = 10, name: str | None = None
    ) -> Callable | None:
        """Register a hook handler. Returns optional unregister callable."""
        self.registered_hooks.append(
            {
                "event": event,
                "handler": handler,
                "priority": priority,
                "name": name,
            }
        )
        return None

    async def emit(self, event_name: str, data):
        """Emit an event."""
        self.emitted_events.append((event_name, data))


@pytest.mark.asyncio
async def test_hook_registration_on_mount(tmp_path):
    """Test that mount registers the visibility hook."""
    coordinator = MockCoordinator()

    # Create test skill
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill for hook testing
---
# Test Content""")

    config = {
        "skills_dir": str(tmp_path),
        "visibility": {
            "enabled": True,
            "inject_role": "user",
        },
    }

    await mount(coordinator, config)

    # Verify hook was registered
    provider_hooks = [
        h
        for h in coordinator.hooks.registered_hooks
        if h["event"] == "provider:request"
    ]
    assert len(provider_hooks) == 1
    assert provider_hooks[0]["name"] == "skills-visibility"
    assert provider_hooks[0]["priority"] == 20


@pytest.mark.asyncio
async def test_hook_disabled_by_config(tmp_path):
    """Test that hook is not registered when disabled."""
    coordinator = MockCoordinator()

    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill
---
# Test""")

    config = {
        "skills_dir": str(tmp_path),
        "visibility": {
            "enabled": False,  # Explicitly disabled
        },
    }

    await mount(coordinator, config)

    # Verify hook was NOT registered
    provider_hooks = [
        h
        for h in coordinator.hooks.registered_hooks
        if h["event"] == "provider:request"
    ]
    assert len(provider_hooks) == 0


@pytest.mark.asyncio
async def test_hook_returns_correct_result(tmp_path):
    """Test that hook returns correct HookResult format."""
    # Create test skills
    skill_dir = tmp_path / "skill-1"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: skill-1
description: First test skill
---
# Content 1""")

    skill_dir2 = tmp_path / "skill-2"
    skill_dir2.mkdir()
    (skill_dir2 / "SKILL.md").write_text("""---
name: skill-2  
description: Second test skill
---
# Content 2""")

    # Discover skills
    from amplifier_module_tool_skills.discovery import discover_skills

    skills = discover_skills(tmp_path)

    # Create hook
    config = {
        "enabled": True,
        "inject_role": "user",
        "max_skills_visible": 50,
        "ephemeral": True,
        "priority": 20,
    }
    hook = SkillsVisibilityHook(skills, config)

    # Call hook
    result = await hook.on_provider_request("provider:request", {})

    # Verify result structure
    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert result.context_injection_role == "user"
    assert result.ephemeral is True

    # Verify content format
    content = result.context_injection
    assert "<system-reminder" in content
    assert "</system-reminder>" in content
    assert "skill-1" in content
    assert "skill-2" in content
    assert "First test skill" in content
    assert "Second test skill" in content


@pytest.mark.asyncio
async def test_hook_handles_no_skills():
    """Test that hook returns continue when no skills available."""
    config = {
        "enabled": True,
        "inject_role": "user",
    }
    hook = SkillsVisibilityHook({}, config)  # Empty skills dict

    result = await hook.on_provider_request("provider:request", {})

    # Should return continue, not inject_context
    assert result.action == "continue"


@pytest.mark.asyncio
async def test_hook_respects_max_visible(tmp_path):
    """Test that hook limits number of visible skills."""
    # Create many skills
    for i in range(10):
        skill_dir = tmp_path / f"skill-{i}"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(f"""---
name: skill-{i}
description: Test skill {i}
---
# Content""")

    from amplifier_module_tool_skills.discovery import discover_skills

    skills = discover_skills(tmp_path)

    # Create hook with small limit
    config = {
        "enabled": True,
        "max_skills_visible": 3,
    }
    hook = SkillsVisibilityHook(skills, config)

    result = await hook.on_provider_request("provider:request", {})

    content = result.context_injection

    # Count skills in output (should be limited to 3)
    skill_count = content.count("skill-")
    assert skill_count == 3

    # Should mention truncation
    assert "more - use load_skill(list=true)" in content


@pytest.mark.asyncio
async def test_hook_injects_as_system_role_by_default(tmp_path):
    """Test that SkillsVisibilityHook uses 'system' as the default inject_role.

    Skills visibility injection is a system-level concern and must default to
    'system' role to ensure proper context scoping by LLM providers.
    """
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill for default role testing
---
# Test Content""")

    from amplifier_module_tool_skills.discovery import discover_skills

    skills = discover_skills(tmp_path)

    # Create hook with no inject_role config — should default to 'system'
    hook = SkillsVisibilityHook(skills, {})

    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection_role == "system"


@pytest.mark.asyncio
async def test_mount_with_visibility_defaults(tmp_path):
    """Test that visibility defaults to enabled."""
    coordinator = MockCoordinator()

    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill
---
# Test""")

    # Config without visibility section - should default to enabled
    config = {"skills_dir": str(tmp_path)}

    await mount(coordinator, config)

    # Verify hook WAS registered (enabled by default)
    provider_hooks = [
        h
        for h in coordinator.hooks.registered_hooks
        if h["event"] == "provider:request"
    ]
    assert len(provider_hooks) == 1


@pytest.mark.asyncio
async def test_cleanup_unregisters_visibility_hook(tmp_path):
    """Test that cleanup() calls the unregister callable for the visibility hook."""
    unregister_calls = []

    class TrackingMockHooks(MockHooks):
        """MockHooks that returns an unregister callable and tracks unregister calls."""

        def register(
            self, event: str, handler, priority: int = 10, name: str | None = None
        ) -> Callable | None:
            """Register a hook handler and return an unregister callable."""
            super().register(event=event, handler=handler, priority=priority, name=name)

            # Return an unregister callable that tracks its call
            def unregister():
                unregister_calls.append(name)

            return unregister

    coordinator = MockCoordinator()
    coordinator.hooks = TrackingMockHooks()

    # Create test skill
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill for unregister testing
---
# Test Content""")

    config = {
        "skills_dir": str(tmp_path),
        "visibility": {
            "enabled": True,
        },
    }

    cleanup = await mount(coordinator, config)
    assert cleanup is not None

    # Verify hook was registered
    assert any(
        h["name"] == "skills-visibility" for h in coordinator.hooks.registered_hooks
    )

    # Verify unregister not yet called
    assert "skills-visibility" not in unregister_calls

    # Call cleanup
    await cleanup()

    # Verify unregister was called for skills-visibility
    assert "skills-visibility" in unregister_calls
