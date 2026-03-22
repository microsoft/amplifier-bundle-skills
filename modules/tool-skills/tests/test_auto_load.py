"""Tests for auto_load frontmatter field and skill:loaded emission at mount time.

Covers the fix for GitHub issue #156: Skills with embedded hooks are discovered
but their hooks never activate because skill:loaded is only emitted when the
agent explicitly calls load_skill().

The fix: skills that set both ``auto-load: true`` AND have a ``hooks:`` block in
their frontmatter now emit ``skill:loaded`` automatically during mount(), causing
hook-shell (and any other listener) to activate the skill-scoped hooks without
requiring the agent to call load_skill().
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from amplifier_module_tool_skills import mount
from amplifier_module_tool_skills.discovery import SkillMetadata, discover_skills


# ---------------------------------------------------------------------------
# Shared mock infrastructure
# ---------------------------------------------------------------------------


class MockHooks:
    """Mock hooks system that tracks emitted events and registered handlers."""

    def __init__(self):
        self.registered_hooks: list[dict] = []
        self.emitted_events: list[tuple[str, dict]] = []

    def register(
        self, event: str, handler, priority: int = 10, name: str | None = None
    ) -> Callable | None:
        self.registered_hooks.append(
            {"event": event, "handler": handler, "priority": priority, "name": name}
        )
        return None

    async def emit(self, event_name: str, data):
        self.emitted_events.append((event_name, data))


class MockCoordinator:
    """Minimal mock coordinator for mount() tests."""

    def __init__(self):
        self.capabilities: dict = {}
        self.mounted_tools: dict = {}
        self.hooks = MockHooks()
        self.config: dict = {}

    def register_capability(self, name: str, value):
        self.capabilities[name] = value

    def get_capability(self, name: str):
        return self.capabilities.get(name)

    async def mount(self, category: str, tool, name: str):
        self.mounted_tools[name] = tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skill_loaded_events(coordinator: MockCoordinator) -> list[dict]:
    """Return all skill:loaded event payloads emitted during mount()."""
    return [
        data
        for name, data in coordinator.hooks.emitted_events
        if name == "skill:loaded"
    ]


def _make_skill(tmp_path: Path, skill_name: str, frontmatter_extra: str = "") -> Path:
    """Create a minimal SKILL.md under tmp_path/<skill_name>/SKILL.md."""
    skill_dir = tmp_path / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: Test skill {skill_name}\n"
        f"{frontmatter_extra}"
        f"---\n# {skill_name}\n\nSkill body content.\n"
    )
    return skill_dir


# ---------------------------------------------------------------------------
# discovery.py unit tests — SkillMetadata.auto_load field
# ---------------------------------------------------------------------------


class TestAutoLoadField:
    """SkillMetadata dataclass and discovery parsing for auto_load."""

    def test_auto_load_default_is_false(self):
        """SkillMetadata.auto_load defaults to False when not in frontmatter."""
        meta = SkillMetadata(
            name="test",
            description="desc",
            path=Path("/tmp/test/SKILL.md"),
            source="/tmp",
        )
        assert meta.auto_load is False

    def test_discover_skills_parses_auto_load_true(self, tmp_path: Path):
        """discover_skills() sets auto_load=True when frontmatter has auto-load: true."""
        _make_skill(
            tmp_path,
            "my-skill",
            frontmatter_extra=(
                "auto-load: true\n"
                "hooks:\n"
                "  shell:\n"
                "    - event: pre-tool\n"
                "      command: echo hook\n"
            ),
        )
        skills = discover_skills(tmp_path)
        assert "my-skill" in skills
        assert skills["my-skill"].auto_load is True

    def test_discover_skills_parses_auto_load_snake_case(self, tmp_path: Path):
        """discover_skills() accepts auto_load (snake_case) in addition to auto-load."""
        _make_skill(
            tmp_path,
            "snake-skill",
            frontmatter_extra=(
                "auto_load: true\n"
                "hooks:\n"
                "  shell:\n"
                "    - event: pre-tool\n"
                "      command: echo hook\n"
            ),
        )
        skills = discover_skills(tmp_path)
        assert skills["snake-skill"].auto_load is True

    def test_discover_skills_auto_load_false_by_default(self, tmp_path: Path):
        """discover_skills() leaves auto_load=False when field absent from frontmatter."""
        _make_skill(tmp_path, "plain-skill")
        skills = discover_skills(tmp_path)
        assert skills["plain-skill"].auto_load is False

    def test_discover_skills_auto_load_false_explicit(self, tmp_path: Path):
        """discover_skills() respects auto-load: false explicitly."""
        _make_skill(
            tmp_path,
            "no-auto-skill",
            frontmatter_extra="auto-load: false\n",
        )
        skills = discover_skills(tmp_path)
        assert skills["no-auto-skill"].auto_load is False


# ---------------------------------------------------------------------------
# mount() integration tests — auto-load loop behaviour
# ---------------------------------------------------------------------------


class TestAutoLoadMount:
    """mount() emits skill:loaded at startup for qualifying skills."""

    @pytest.mark.asyncio
    async def test_skill_with_auto_load_and_hooks_emits_skill_loaded(
        self, tmp_path: Path
    ):
        """mount() emits skill:loaded for a skill with auto_load: true AND hooks."""
        _make_skill(
            tmp_path,
            "hook-skill",
            frontmatter_extra=(
                "auto-load: true\n"
                "hooks:\n"
                "  shell:\n"
                "    - event: pre-tool\n"
                "      command: echo quality-gate\n"
            ),
        )
        coordinator = MockCoordinator()
        await mount(coordinator, {"skills_dir": str(tmp_path)})

        loaded = _skill_loaded_events(coordinator)
        assert len(loaded) == 1
        assert loaded[0]["skill_name"] == "hook-skill"

    @pytest.mark.asyncio
    async def test_skill_with_auto_load_but_no_hooks_does_not_emit(
        self, tmp_path: Path
    ):
        """mount() does NOT emit skill:loaded for auto_load: true without hooks."""
        _make_skill(
            tmp_path,
            "no-hook-skill",
            frontmatter_extra="auto-load: true\n",
        )
        coordinator = MockCoordinator()
        await mount(coordinator, {"skills_dir": str(tmp_path)})

        loaded = _skill_loaded_events(coordinator)
        assert loaded == []

    @pytest.mark.asyncio
    async def test_skill_with_hooks_but_no_auto_load_does_not_emit(
        self, tmp_path: Path
    ):
        """mount() does NOT emit skill:loaded for a skill with hooks but no auto_load."""
        _make_skill(
            tmp_path,
            "hooks-only-skill",
            frontmatter_extra=(
                "hooks:\n  shell:\n    - event: pre-tool\n      command: echo gate\n"
            ),
        )
        coordinator = MockCoordinator()
        await mount(coordinator, {"skills_dir": str(tmp_path)})

        loaded = _skill_loaded_events(coordinator)
        assert loaded == []

    @pytest.mark.asyncio
    async def test_auto_loaded_event_has_auto_loaded_true_field(self, tmp_path: Path):
        """The skill:loaded event emitted by auto-load contains auto_loaded: True."""
        _make_skill(
            tmp_path,
            "flagged-skill",
            frontmatter_extra=(
                "auto-load: true\n"
                "hooks:\n"
                "  shell:\n"
                "    - event: pre-tool\n"
                "      command: echo gate\n"
            ),
        )
        coordinator = MockCoordinator()
        await mount(coordinator, {"skills_dir": str(tmp_path)})

        loaded = _skill_loaded_events(coordinator)
        assert len(loaded) == 1
        assert loaded[0].get("auto_loaded") is True

    @pytest.mark.asyncio
    async def test_auto_loaded_skill_is_in_loaded_skills_set(self, tmp_path: Path):
        """Auto-loaded skills appear in tool.loaded_skills so cleanup emits skill:unloaded."""
        _make_skill(
            tmp_path,
            "tracked-skill",
            frontmatter_extra=(
                "auto-load: true\n"
                "hooks:\n"
                "  shell:\n"
                "    - event: pre-tool\n"
                "      command: echo gate\n"
            ),
        )
        coordinator = MockCoordinator()
        await mount(coordinator, {"skills_dir": str(tmp_path)})

        # The tool is mounted under its name
        tool = coordinator.mounted_tools.get("load_skill")
        assert tool is not None
        assert "tracked-skill" in tool.loaded_skills

    @pytest.mark.asyncio
    async def test_existing_skills_without_auto_load_unchanged(self, tmp_path: Path):
        """Skills without auto_load continue to work exactly as before (no spurious events)."""
        _make_skill(tmp_path, "normal-skill")
        coordinator = MockCoordinator()
        await mount(coordinator, {"skills_dir": str(tmp_path)})

        # No skill:loaded events should be emitted at mount for non-auto_load skills
        loaded = _skill_loaded_events(coordinator)
        assert loaded == []

        # skills:discovered IS still emitted
        discovered = [
            data
            for name, data in coordinator.hooks.emitted_events
            if name == "skills:discovered"
        ]
        assert len(discovered) == 1
        assert "normal-skill" in discovered[0]["skill_names"]

    @pytest.mark.asyncio
    async def test_auto_loaded_event_payload_matches_explicit_load_shape(
        self, tmp_path: Path
    ):
        """The auto-load event payload contains all fields present in _load_skill() emit."""
        frontmatter_extra = (
            "version: 1.2.3\n"
            "auto-load: true\n"
            "hooks:\n"
            "  shell:\n"
            "    - event: pre-tool\n"
            "      command: echo gate\n"
        )
        _make_skill(tmp_path, "full-skill", frontmatter_extra=frontmatter_extra)
        coordinator = MockCoordinator()
        await mount(coordinator, {"skills_dir": str(tmp_path)})

        loaded = _skill_loaded_events(coordinator)
        assert len(loaded) == 1
        payload = loaded[0]

        # All fields that _load_skill() emits must be present
        required_fields = {
            "skill_name",
            "source",
            "content_length",
            "version",
            "skill_directory",
            "hooks",
            "context",
            "allowed_tools",
            "disable_model_invocation",
            "user_invocable",
            "slash_command",
        }
        missing = required_fields - payload.keys()
        assert not missing, f"Missing fields in auto-load event payload: {missing}"

        # Extra auto-load marker
        assert payload["auto_loaded"] is True
        assert payload["skill_name"] == "full-skill"
        assert payload["version"] == "1.2.3"
        assert payload["hooks"] is not None
        assert isinstance(payload["content_length"], int)
        assert payload["content_length"] > 0

    @pytest.mark.asyncio
    async def test_multiple_auto_load_skills_each_emit(self, tmp_path: Path):
        """Every qualifying skill (auto_load + hooks) gets its own skill:loaded event."""
        for i in range(3):
            _make_skill(
                tmp_path,
                f"auto-skill-{i}",
                frontmatter_extra=(
                    "auto-load: true\n"
                    "hooks:\n"
                    "  shell:\n"
                    f"    - event: pre-tool\n"
                    f"      command: echo gate-{i}\n"
                ),
            )
        # Add one non-qualifying skill to verify it's not included
        _make_skill(tmp_path, "plain-skill")

        coordinator = MockCoordinator()
        await mount(coordinator, {"skills_dir": str(tmp_path)})

        loaded = _skill_loaded_events(coordinator)
        assert len(loaded) == 3
        loaded_names = {e["skill_name"] for e in loaded}
        assert loaded_names == {"auto-skill-0", "auto-skill-1", "auto-skill-2"}

    @pytest.mark.asyncio
    async def test_cleanup_emits_skill_unloaded_for_auto_loaded_skill(
        self, tmp_path: Path
    ):
        """cleanup() emits skill:unloaded for auto-loaded skills (they're in loaded_skills)."""
        _make_skill(
            tmp_path,
            "cleanup-skill",
            frontmatter_extra=(
                "auto-load: true\n"
                "hooks:\n"
                "  shell:\n"
                "    - event: pre-tool\n"
                "      command: echo gate\n"
            ),
        )
        coordinator = MockCoordinator()
        cleanup = await mount(coordinator, {"skills_dir": str(tmp_path)})
        assert cleanup is not None

        # Call cleanup
        await cleanup()

        unloaded = [
            data
            for name, data in coordinator.hooks.emitted_events
            if name == "skill:unloaded"
        ]
        assert len(unloaded) == 1
        assert unloaded[0]["skill_name"] == "cleanup-skill"
