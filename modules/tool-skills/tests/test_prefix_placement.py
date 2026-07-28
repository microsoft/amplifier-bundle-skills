"""Tests for visibility.placement — skills index in the stable system-prompt prefix.

placement="request" (default) is today's behavior byte-identical: per-request
inject_context. placement="prefix" wraps the context module's system-prompt
factory (the surface amplifier-foundation _prepared.py registers via
context.set_system_prompt_factory) so the index rides the provider-cached
system block instead of being re-sent as fresh input tokens every request.
"""

from pathlib import Path
from typing import Any

import pytest

from amplifier_module_tool_skills.discovery import SkillMetadata
from amplifier_module_tool_skills.hooks import SkillsVisibilityHook


@pytest.fixture
def sample_skills():
    """Sample skills for testing."""
    return {
        "python-testing": SkillMetadata(
            name="python-testing",
            description="Best practices for Python testing with pytest",
            path=Path("/skills/python-testing/SKILL.md"),
            source="/skills",
        ),
        "git-workflow": SkillMetadata(
            name="git-workflow",
            description="Git branching and commit message standards",
            path=Path("/skills/git-workflow/SKILL.md"),
            source="/skills",
        ),
    }


@pytest.fixture
def fork_skills():
    """Catalog containing a fork-context skill (must be hidden in forked sessions)."""
    return {
        "normal-skill": SkillMetadata(
            name="normal-skill",
            description="A normal skill",
            path=Path("/skills/normal-skill/SKILL.md"),
            source="/skills",
        ),
        "forked-skill": SkillMetadata(
            name="forked-skill",
            description="A fork-context skill",
            path=Path("/skills/forked-skill/SKILL.md"),
            source="/skills",
            context="fork",
        ),
    }


class FakeContext:
    """Context module exposing the system-prompt-factory surface
    (context-simple shape: public async setter, private attribute)."""

    def __init__(self, base_prompt: str = "BASE SYSTEM PROMPT"):
        self._system_prompt_factory = self._make_base(base_prompt)

    def _make_base(self, text: str):
        async def _base() -> str:
            return text

        return _base

    async def set_system_prompt_factory(self, factory) -> None:
        self._system_prompt_factory = factory


class FakeCoordinator:
    """Coordinator exposing .get('context') and get_capability (hook needs both)."""

    def __init__(self, context=None):
        self._context = context

    def get(self, name: str):
        return self._context if name == "context" else None

    def get_capability(self, name: str):
        return None


def fake_coordinator(context=None) -> Any:
    """Typed-as-Any constructor so the duck-typed mock passes the hook's
    ModuleCoordinator annotation (same duck-typing the hook itself relies on)."""
    return FakeCoordinator(context)


# ---------------------------------------------------------------------------
# Default mode — regression: behavior byte-identical to pre-placement code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_mode_unchanged(sample_skills):
    """No placement key -> per-request inject_context, exactly as before."""
    hook = SkillsVisibilityHook(sample_skills, {})
    assert hook.placement == "request"
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert (
        '<system-reminder source="hooks-skills-visibility">' in result.context_injection
    )
    assert "python-testing" in result.context_injection
    assert result.context_injection_role == "system"  # pre-existing default
    assert result.ephemeral is True
    assert result.suppress_output is True


@pytest.mark.asyncio
async def test_explicit_request_placement_identical(sample_skills):
    """placement='request' is the same as omitting the key."""
    implicit = SkillsVisibilityHook(sample_skills, {})
    explicit = SkillsVisibilityHook(sample_skills, {"placement": "request"})
    r1 = await implicit.on_provider_request("provider:request", {})
    r2 = await explicit.on_provider_request("provider:request", {})
    assert r1.action == r2.action == "inject_context"
    assert r1.context_injection == r2.context_injection


def test_invalid_placement_rejected(sample_skills):
    """Unknown placement value fails loudly at construction, not mid-session."""
    with pytest.raises(ValueError, match="placement"):
        SkillsVisibilityHook(sample_skills, {"placement": "sideways"})


# ---------------------------------------------------------------------------
# Prefix mode — placement, refresh-on-change, no-double-inject, fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prefix_mode_places_index_in_system_prompt(sample_skills):
    """Prefix mode: factory output = base + skills block; hook injects nothing."""
    context = FakeContext()
    hook = SkillsVisibilityHook(
        sample_skills,
        {"placement": "prefix"},
        coordinator=fake_coordinator(context),
    )
    result = await hook.on_provider_request("provider:request", {})

    # Never a per-request injection in prefix mode (no double-inject).
    assert result.action == "continue"

    rendered = await context._system_prompt_factory()
    assert rendered.startswith("BASE SYSTEM PROMPT")
    assert '<system-reminder source="hooks-skills-visibility">' in rendered
    assert "python-testing" in rendered
    assert "git-workflow" in rendered


@pytest.mark.asyncio
async def test_prefix_mode_stable_across_requests(sample_skills):
    """Unchanged catalog -> byte-identical system prompt (cacheable prefix),
    and the cached render object is reused (no re-render)."""
    context = FakeContext()
    hook = SkillsVisibilityHook(
        sample_skills,
        {"placement": "prefix"},
        coordinator=fake_coordinator(context),
    )
    await hook.on_provider_request("provider:request", {})
    first = await context._system_prompt_factory()
    block_obj = hook._prefix_rendered
    await hook.on_provider_request("provider:request", {})
    second = await context._system_prompt_factory()
    assert first == second
    assert hook._prefix_rendered is block_obj  # cached, not re-rendered


@pytest.mark.asyncio
async def test_prefix_mode_refreshes_on_catalog_change(sample_skills):
    """Skills change mid-session (mode overlays) -> prefix holds exactly the
    CURRENT catalog: new skill appears, removed skill disappears. No stale copies."""
    context = FakeContext()
    hook = SkillsVisibilityHook(
        sample_skills,
        {"placement": "prefix"},
        coordinator=fake_coordinator(context),
    )
    await hook.on_provider_request("provider:request", {})
    before = await context._system_prompt_factory()
    assert "python-testing" in before

    # Simulate a runtime overlay change (the dict is the hook's catalog ref).
    sample_skills["new-mode-skill"] = SkillMetadata(
        name="new-mode-skill",
        description="Contributed by an active mode",
        path=Path("/skills/new-mode-skill/SKILL.md"),
        source="/skills",
    )
    del sample_skills["git-workflow"]

    after = await context._system_prompt_factory()
    assert "new-mode-skill" in after
    assert "git-workflow" not in after
    # Exactly one copy of the index in the prompt.
    assert after.count('<system-reminder source="hooks-skills-visibility">') == 1


@pytest.mark.asyncio
async def test_prefix_mode_rewraps_after_factory_rereg(sample_skills):
    """If someone re-registers a new base factory after our wrap, the next
    request re-wraps around it — the index never silently disappears."""
    context = FakeContext()
    hook = SkillsVisibilityHook(
        sample_skills,
        {"placement": "prefix"},
        coordinator=fake_coordinator(context),
    )
    await hook.on_provider_request("provider:request", {})

    async def new_base() -> str:
        return "REPLACED BASE"

    await context.set_system_prompt_factory(new_base)  # clobbers our wrap
    await hook.on_provider_request("provider:request", {})
    rendered = await context._system_prompt_factory()
    assert rendered.startswith("REPLACED BASE")
    assert "python-testing" in rendered
    assert rendered.count('<system-reminder source="hooks-skills-visibility">') == 1


@pytest.mark.asyncio
async def test_prefix_mode_fork_filtering_applies(fork_skills):
    """Fork-context skills stay hidden from forked sub-sessions in prefix mode."""
    context = FakeContext()
    hook = SkillsVisibilityHook(
        fork_skills,
        {"placement": "prefix"},
        is_forked_session=True,
        coordinator=fake_coordinator(context),
    )
    await hook.on_provider_request("provider:request", {})
    rendered = await context._system_prompt_factory()
    assert "normal-skill" in rendered
    assert "forked-skill" not in rendered


@pytest.mark.asyncio
async def test_prefix_mode_falls_back_loudly_without_surface(sample_skills, caplog):
    """No context module -> ERROR log + request-mode injection (agent never
    silently loses skill visibility; the misplacement is detectable)."""
    hook = SkillsVisibilityHook(
        sample_skills,
        {"placement": "prefix"},
        coordinator=fake_coordinator(None),
    )
    with caplog.at_level("ERROR"):
        result = await hook.on_provider_request("provider:request", {})
    assert result.action == "inject_context"  # fallback, not silence
    assert any("prefix" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_prefix_mode_refuses_to_replace_static_prompt(sample_skills):
    """A session with NO registered factory (static system messages) must not
    have its prompt replaced by a skills-only factory — falls back."""
    context = FakeContext()
    context._system_prompt_factory = None
    hook = SkillsVisibilityHook(
        sample_skills,
        {"placement": "prefix"},
        coordinator=fake_coordinator(context),
    )
    result = await hook.on_provider_request("provider:request", {})
    assert result.action == "inject_context"  # request-mode fallback
    assert context._system_prompt_factory is None  # untouched


@pytest.mark.asyncio
async def test_prefix_mode_disabled_still_respected(sample_skills):
    """enabled=false wins over placement — nothing wrapped, nothing injected."""
    context = FakeContext()
    hook = SkillsVisibilityHook(
        sample_skills,
        {"placement": "prefix", "enabled": False},
        coordinator=fake_coordinator(context),
    )
    result = await hook.on_provider_request("provider:request", {})
    assert result.action == "continue"
    rendered = await context._system_prompt_factory()
    assert "hooks-skills-visibility" not in rendered
