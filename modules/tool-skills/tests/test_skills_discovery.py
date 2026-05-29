"""Tests for SkillsDiscovery class."""

from pathlib import Path

import pytest

from amplifier_module_tool_skills import SkillsDiscovery
from amplifier_module_tool_skills.discovery import SkillMetadata


def _make_skill(
    name: str,
    description: str,
    user_invocable: bool = False,
    context: str | None = None,
    shortcut: str | None = None,
) -> SkillMetadata:
    """Helper to create test SkillMetadata."""
    return SkillMetadata(
        name=name,
        description=description,
        path=Path(f"/fake/{name}/SKILL.md"),
        source="/fake",
        user_invocable=user_invocable,
        context=context,
        shortcut=shortcut,
    )


class TestSkillsDiscoveryListSkills:
    """Tests for SkillsDiscovery.list_skills()."""

    def test_returns_name_description_pairs(self):
        """list_skills() returns (name, description) tuples."""
        skills = {
            "my-skill": _make_skill("my-skill", "A test skill"),
        }
        discovery = SkillsDiscovery(skills)
        result = discovery.list_skills()
        assert ("my-skill", "A test skill") in result

    def test_sorted_alphabetically(self):
        """list_skills() returns pairs sorted alphabetically by name."""
        skills = {
            "zebra-skill": _make_skill("zebra-skill", "Zebra"),
            "apple-skill": _make_skill("apple-skill", "Apple"),
            "mango-skill": _make_skill("mango-skill", "Mango"),
        }
        discovery = SkillsDiscovery(skills)
        result = discovery.list_skills()
        names = [name for name, _ in result]
        assert names == sorted(names)

    def test_includes_all_skills(self):
        """list_skills() includes all skills in the dict."""
        skills = {
            "skill-a": _make_skill("skill-a", "A"),
            "skill-b": _make_skill("skill-b", "B"),
            "skill-c": _make_skill("skill-c", "C"),
        }
        discovery = SkillsDiscovery(skills)
        result = discovery.list_skills()
        assert len(result) == 3

    def test_handles_empty(self):
        """list_skills() returns empty list when no skills."""
        discovery = SkillsDiscovery({})
        result = discovery.list_skills()
        assert result == []


class TestSkillsDiscoveryFind:
    """Tests for SkillsDiscovery.find()."""

    def test_finds_existing_skill(self):
        """find() returns SkillMetadata for existing skill."""
        skill = _make_skill("my-skill", "A test skill")
        skills = {"my-skill": skill}
        discovery = SkillsDiscovery(skills)
        result = discovery.find("my-skill")
        assert result is skill

    def test_returns_none_for_missing(self):
        """find() returns None for non-existent skill."""
        discovery = SkillsDiscovery({"my-skill": _make_skill("my-skill", "Test")})
        result = discovery.find("nonexistent")
        assert result is None


class TestSkillsDiscoveryGetShortcuts:
    """Tests for SkillsDiscovery.get_shortcuts()."""

    def test_returns_only_user_invocable(self):
        """get_shortcuts() returns only skills with user_invocable=True as keys."""
        skills = {
            "public-skill": _make_skill("public-skill", "Public", user_invocable=True),
            "private-skill": _make_skill(
                "private-skill", "Private", user_invocable=False
            ),
        }
        discovery = SkillsDiscovery(skills)
        result = discovery.get_shortcuts()
        assert "public-skill" in result
        assert "private-skill" not in result

    def test_has_required_keys(self):
        """Each shortcut value dict has 'description' and 'context' keys."""
        skills = {
            "public-skill": _make_skill("public-skill", "Public", user_invocable=True),
        }
        discovery = SkillsDiscovery(skills)
        result = discovery.get_shortcuts()
        assert len(result) == 1
        shortcut = result["public-skill"]
        assert "description" in shortcut
        assert "context" in shortcut

    def test_description_matches_metadata(self):
        """Shortcut description matches SkillMetadata.description."""
        skills = {
            "my-skill": _make_skill("my-skill", "My description", user_invocable=True),
        }
        discovery = SkillsDiscovery(skills)
        result = discovery.get_shortcuts()
        assert result["my-skill"]["description"] == "My description"

    def test_empty_when_none_user_invocable(self):
        """get_shortcuts() returns empty dict when no user_invocable skills."""
        skills = {
            "private-skill": _make_skill(
                "private-skill", "Private", user_invocable=False
            ),
        }
        discovery = SkillsDiscovery(skills)
        result = discovery.get_shortcuts()
        assert result == {}

    # --- Required regression-guard tests ---

    def test_method_exists_on_class(self):
        """get_shortcuts exists on SkillsDiscovery and is callable."""
        assert hasattr(SkillsDiscovery, "get_shortcuts")
        assert callable(SkillsDiscovery({}).get_shortcuts)

    def test_empty_skills_dict_returns_empty_dict(self):
        """get_shortcuts() returns empty dict when skills dict is empty."""
        assert SkillsDiscovery({}).get_shortcuts() == {}

    def test_entry_has_name_key(self):
        """Each shortcut entry dict contains the canonical 'name' key."""
        skills = {
            "foo": _make_skill("foo", "Foo skill", user_invocable=True),
        }
        discovery = SkillsDiscovery(skills)
        result = discovery.get_shortcuts()
        assert result["foo"]["name"] == "foo"

    def test_shortcut_registers_alias_key(self):
        """A skill with shortcut != name gets entries under both keys."""
        skills = {
            "cranky-old-sam": _make_skill(
                "cranky-old-sam",
                "Cranky reviewer",
                user_invocable=True,
                shortcut="cosam",
            ),
        }
        discovery = SkillsDiscovery(skills)
        result = discovery.get_shortcuts()
        assert "cranky-old-sam" in result
        assert "cosam" in result
        assert result["cranky-old-sam"]["name"] == "cranky-old-sam"
        assert result["cosam"]["name"] == "cranky-old-sam"

    def test_shortcut_equal_to_canonical_name_is_idempotent(self):
        """A skill with shortcut == name produces only one entry, no errors."""
        skills = {
            "foo": _make_skill("foo", "Foo skill", user_invocable=True, shortcut="foo"),
        }
        discovery = SkillsDiscovery(skills)
        result = discovery.get_shortcuts()
        assert len(result) == 1
        assert "foo" in result


class MockHooks:
    """Minimal mock hooks system for testing."""

    def __init__(self):
        self.emitted_events = []
        self.registered_hooks = []

    def register(self, event: str, handler, priority: int = 10, name: str = None):
        """Register a hook handler."""
        self.registered_hooks.append({"event": event, "handler": handler})
        return lambda: None  # Return unregister callable

    async def emit(self, event_name: str, data):
        """Emit an event."""
        self.emitted_events.append((event_name, data))


class MockCoordinator:
    """Minimal mock coordinator for testing register_capability."""

    def __init__(self):
        self.capabilities: dict = {}
        self.hooks = MockHooks()
        self.config = {}

    def register_capability(self, name: str, value) -> None:
        """Register a capability."""
        self.capabilities[name] = value

    def get_capability(self, name: str):
        """Get a capability."""
        return self.capabilities.get(name)

    def get(self, name: str):
        """Get a component."""
        return None

    async def mount(self, category: str, tool, name: str):
        """Mount a tool."""


class TestSkillsDiscoveryRegistration:
    """Tests that mount() registers SkillsDiscovery as a coordinator capability."""

    @pytest.mark.asyncio
    async def test_mount_registers_skills_discovery_capability(self, tmp_path):
        """mount() calls coordinator.register_capability('skills_discovery', ...)."""
        from amplifier_module_tool_skills import mount

        coordinator = MockCoordinator()
        config = {"skills_dir": str(tmp_path)}

        await mount(coordinator, config)

        # Verify register_capability was called with 'skills_discovery'
        assert "skills_discovery" in coordinator.capabilities, (
            "mount() must call coordinator.register_capability('skills_discovery', ...)"
        )

    @pytest.mark.asyncio
    async def test_registered_skills_discovery_has_list_skills_method(self, tmp_path):
        """Registered SkillsDiscovery object has list_skills method."""
        from amplifier_module_tool_skills import mount

        coordinator = MockCoordinator()
        config = {"skills_dir": str(tmp_path)}

        await mount(coordinator, config)

        sd = coordinator.capabilities.get("skills_discovery")
        assert sd is not None
        assert hasattr(sd, "list_skills"), (
            "SkillsDiscovery must have list_skills method"
        )

    @pytest.mark.asyncio
    async def test_registered_skills_discovery_has_find_method(self, tmp_path):
        """Registered SkillsDiscovery object has find method."""
        from amplifier_module_tool_skills import mount

        coordinator = MockCoordinator()
        config = {"skills_dir": str(tmp_path)}

        await mount(coordinator, config)

        sd = coordinator.capabilities.get("skills_discovery")
        assert sd is not None
        assert hasattr(sd, "find"), "SkillsDiscovery must have find method"

    @pytest.mark.asyncio
    async def test_registered_skills_discovery_has_get_shortcuts_method(self, tmp_path):
        """Registered SkillsDiscovery object has get_shortcuts method."""
        from amplifier_module_tool_skills import mount

        coordinator = MockCoordinator()
        config = {"skills_dir": str(tmp_path)}

        await mount(coordinator, config)

        sd = coordinator.capabilities.get("skills_discovery")
        assert sd is not None
        assert hasattr(sd, "get_shortcuts"), (
            "SkillsDiscovery must have get_shortcuts method"
        )
