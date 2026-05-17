"""Tests for runtime_skill_overlay capability in search and list operations.

Issue #233: mode-contributed skills via contributes.skills must be discoverable
by tool-skills in both list and search operations. The bridge is the
`runtime_skill_overlay` coordinator capability — a list of URIs that the
mention_resolver resolves to skill directories at query time.
"""

from pathlib import Path

from amplifier_module_tool_skills import SkillsTool
from amplifier_module_tool_skills.discovery import SkillMetadata

RUNTIME_SKILL_OVERLAY_CAPABILITY = "runtime_skill_overlay"


class MockCoordinator:
    """Minimal mock coordinator for overlay-skills tests."""

    def __init__(self) -> None:
        self.capabilities: dict = {}
        self.config: dict = {}

    def register_capability(self, name: str, value: object) -> None:
        self.capabilities[name] = value

    def get_capability(self, name: str) -> object:
        return self.capabilities.get(name)


class MockResolver:
    """Resolve @uri strings to local directory paths for testing."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    def resolve(self, uri: str) -> str | None:
        return self._mapping.get(uri)


def _make_overlay_skill_dir(
    tmp_path: Path, name: str, description: str
) -> tuple[Path, str]:
    """Write a SKILL.md to tmp_path/<name>/ and return (skill_dir, uri)."""
    skill_dir = tmp_path / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\nSkill body.\n"
    )
    uri = f"@overlay:{name}"
    return skill_dir, uri


def test_overlay_skill_appears_in_list_skills(tmp_path: Path) -> None:
    """Overlay skill from runtime_skill_overlay capability appears in _list_skills."""
    skill_dir, uri = _make_overlay_skill_dir(
        tmp_path, "overlay-skill-a", "An overlay skill for testing"
    )

    coordinator = MockCoordinator()
    coordinator.register_capability(RUNTIME_SKILL_OVERLAY_CAPABILITY, [uri])
    coordinator.register_capability(
        "mention_resolver", MockResolver({uri: str(skill_dir)})
    )

    tool = SkillsTool({}, coordinator, [])  # type: ignore[arg-type]
    result = tool._list_skills()

    assert result.success
    assert result.output is not None
    assert "overlay-skill-a" in result.output["message"]
    skill_names = [s["name"] for s in result.output["skills"]]
    assert "overlay-skill-a" in skill_names


def test_overlay_skill_found_by_search_skills(tmp_path: Path) -> None:
    """Overlay skill is found when searching by name via _search_skills."""
    skill_dir, uri = _make_overlay_skill_dir(
        tmp_path, "overlay-skill-b", "An overlay skill for searching"
    )

    coordinator = MockCoordinator()
    coordinator.register_capability(RUNTIME_SKILL_OVERLAY_CAPABILITY, [uri])
    coordinator.register_capability(
        "mention_resolver", MockResolver({uri: str(skill_dir)})
    )

    tool = SkillsTool({}, coordinator, [])  # type: ignore[arg-type]
    result = tool._search_skills("overlay-skill-b")

    assert result.success
    assert result.output is not None
    assert "matches" in result.output
    match_names = [m["name"] for m in result.output["matches"]]
    assert "overlay-skill-b" in match_names


def test_local_skills_shadow_overlay_on_conflict(tmp_path: Path) -> None:
    """Local skill named X shadows an overlay skill with the same name X.

    _get_overlay_skill_metadata() skips any URI that resolves to a skill
    already present in self.skills. The local (static) version wins.
    """
    conflict_name = "conflict-skill"

    # Create the overlay version of the skill on disk
    overlay_dir, uri = _make_overlay_skill_dir(
        tmp_path, conflict_name, "Overlay description — should not win"
    )

    coordinator = MockCoordinator()
    coordinator.register_capability(RUNTIME_SKILL_OVERLAY_CAPABILITY, [uri])
    coordinator.register_capability(
        "mention_resolver", MockResolver({uri: str(overlay_dir)})
    )

    tool = SkillsTool({}, coordinator, [])  # type: ignore[arg-type]
    # Inject a "local" skill with the same name directly (simulates static
    # mount-time discovery; local skills are first-match-wins over overlay).
    local_skill_path = tmp_path / "local" / "SKILL.md"
    local_skill_path.parent.mkdir(parents=True)
    local_skill_path.write_text("")
    tool.skills[conflict_name] = SkillMetadata(
        name=conflict_name,
        description="Local description — this wins",
        path=local_skill_path,
        source="local",
    )

    result = tool._list_skills()

    assert result.success
    assert result.output is not None
    skill_names = [s["name"] for s in result.output["skills"]]
    assert conflict_name in skill_names

    # Verify the LOCAL description wins, not the overlay's
    winning_entry = next(
        s for s in result.output["skills"] if s["name"] == conflict_name
    )
    assert winning_entry["description"] == "Local description — this wins"


def test_no_overlay_capability_baseline(tmp_path: Path) -> None:  # noqa: ARG001
    """Without runtime_skill_overlay capability, list and search work as before.

    No coordinator, or coordinator without the capability, must not break
    existing behavior. This is the regression guard for the no-mode case.
    """
    # Case 1: coordinator present but capability NOT registered
    coordinator = MockCoordinator()
    tool = SkillsTool({}, coordinator, [])  # type: ignore[arg-type]
    result = tool._list_skills()
    # No skills → empty-skills path (success, no crash)
    assert result.success

    # Case 2: no coordinator at all
    tool_no_coord = SkillsTool({}, None, [])
    result2 = tool_no_coord._list_skills()
    assert result2.success

    # Case 3: search also works cleanly with no overlay
    result3 = tool._search_skills("anything")
    assert result3.success


# ============================================================================
# Tests for full coverage of overlay-aware entry points
# ============================================================================
# Issue #233 part 2: list and search were the first entry points wired to
# consult runtime_skill_overlay; load_skill, get_skill_info, and the
# visibility hook also need to see overlay skills so a contributed skill
# is consistently discoverable end-to-end while the contributing mode is
# active.


def test_overlay_skill_found_by_load_skill(tmp_path: Path) -> None:
    """_load_skill resolves an overlay-only skill (not in local catalog).

    Without overlay-awareness in _load_skill, load_skill(skill_name=...)
    would return "not found" even though the skill is mounted via the
    runtime_skill_overlay capability. This is the fix for the user-visible
    'load_skill cannot find mode-contributed skill' bug.
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    overlay_dir, uri = _make_overlay_skill_dir(
        tmp_path, "overlay-loadable", "Loadable via overlay only"
    )

    coordinator = MockCoordinator()
    coordinator.register_capability(RUNTIME_SKILL_OVERLAY_CAPABILITY, [uri])
    coordinator.register_capability(
        "mention_resolver", MockResolver({uri: str(overlay_dir)})
    )
    # _load_skill emits a 'skill:loaded' event via coordinator.hooks.emit
    # after a successful load. Provide an async-compatible hooks mock so
    # the test doesn't crash on the post-load notification.
    coordinator.hooks = MagicMock()  # type: ignore[attr-defined]
    coordinator.hooks.emit = AsyncMock()  # type: ignore[attr-defined]

    tool = SkillsTool({}, coordinator, [])  # type: ignore[arg-type]
    result = asyncio.run(tool._load_skill("overlay-loadable"))

    assert result.success, f"Expected success, got error: {result.error}"
    # The emit() call confirms the load reached the success path.
    coordinator.hooks.emit.assert_awaited_once()  # type: ignore[attr-defined]
    args, _ = coordinator.hooks.emit.call_args  # type: ignore[attr-defined]
    assert args[0] == "skill:loaded"
    assert args[1]["skill_name"] == "overlay-loadable"


def test_overlay_skill_found_by_get_skill_info(tmp_path: Path) -> None:
    """_get_skill_info resolves an overlay-only skill.

    load_skill(info='name') must produce metadata for overlay skills, not
    'not found'. Same fix as _load_skill, different entry point.
    """
    overlay_dir, uri = _make_overlay_skill_dir(
        tmp_path, "overlay-infoable", "Info via overlay"
    )

    coordinator = MockCoordinator()
    coordinator.register_capability(RUNTIME_SKILL_OVERLAY_CAPABILITY, [uri])
    coordinator.register_capability(
        "mention_resolver", MockResolver({uri: str(overlay_dir)})
    )

    tool = SkillsTool({}, coordinator, [])  # type: ignore[arg-type]
    result = tool._get_skill_info("overlay-infoable")

    assert result.success, f"Expected success, got error: {result.error}"
    assert result.output is not None
    assert result.output["name"] == "overlay-infoable"
    assert result.output["description"] == "Info via overlay"


def test_overlay_skill_load_skill_not_found_when_no_overlay(tmp_path: Path) -> None:  # noqa: ARG001
    """_load_skill returns 'not found' for a skill absent from both catalogs.

    Regression guard: the overlay-aware error path must still report
    'not found' (with the merged available list) when the requested skill
    truly does not exist anywhere.
    """
    import asyncio

    coordinator = MockCoordinator()
    tool = SkillsTool({}, coordinator, [])  # type: ignore[arg-type]
    result = asyncio.run(tool._load_skill("nonexistent"))

    assert not result.success
    assert result.error is not None
    assert "not found" in result.error["message"].lower()


def test_visibility_hook_renders_overlay_skills(tmp_path: Path) -> None:
    """SkillsVisibilityHook surfaces overlay skills when constructed with a tool.

    The hook's job is to emit the available-skills system reminder on every
    provider:request. Without tool-attached overlay merging, mode-contributed
    skills are invisible to the LLM (the visibility hook only saw the static
    mount-time catalog).
    """
    from amplifier_module_tool_skills.hooks import SkillsVisibilityHook

    overlay_dir, uri = _make_overlay_skill_dir(
        tmp_path, "overlay-visible", "Should appear in visibility output"
    )

    coordinator = MockCoordinator()
    coordinator.register_capability(RUNTIME_SKILL_OVERLAY_CAPABILITY, [uri])
    coordinator.register_capability(
        "mention_resolver", MockResolver({uri: str(overlay_dir)})
    )

    tool = SkillsTool({}, coordinator, [])  # type: ignore[arg-type]

    # Construct hook the way __init__.py mounts it now — with tool reference.
    # type: ignore[call-arg] — pyright sometimes lags on freshly-added kwargs
    hook = SkillsVisibilityHook(  # type: ignore[call-arg]
        skills=tool.skills,
        config={"enabled": True},
        coordinator=coordinator,  # type: ignore[arg-type]
        tool=tool,
    )

    rendered = hook._format_skills_list()
    assert "overlay-visible" in rendered, (
        f"Expected overlay-visible skill in rendered visibility output, got:\n{rendered}"
    )
    assert "Should appear in visibility output" in rendered


def test_visibility_hook_legacy_path_unchanged(tmp_path: Path) -> None:  # noqa: ARG001
    """Hook without `tool` keeps the legacy static-only behavior.

    Backward-compatibility guard: many existing tests construct the hook
    with just (skills, config). Those callers must not be required to pass
    a tool reference. The hook should fall back to the static skills dict
    when no tool is attached.
    """
    from amplifier_module_tool_skills.hooks import SkillsVisibilityHook
    from amplifier_module_tool_skills.discovery import SkillMetadata

    static_skills = {
        "static-only": SkillMetadata(
            name="static-only",
            description="Static catalog entry",
            path=Path("/nonexistent/SKILL.md"),
            source="local",
        )
    }
    hook = SkillsVisibilityHook(skills=static_skills, config={"enabled": True})

    rendered = hook._format_skills_list()
    assert "static-only" in rendered
