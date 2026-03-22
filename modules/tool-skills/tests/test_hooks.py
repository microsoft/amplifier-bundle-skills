"""Tests for skills visibility hook."""

import pytest
from pathlib import Path
from amplifier_module_tool_skills.hooks import SkillsVisibilityHook
from amplifier_module_tool_skills.discovery import SkillMetadata


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
        "api-design": SkillMetadata(
            name="api-design",
            description="RESTful API design patterns and conventions",
            path=Path("/skills/api-design/SKILL.md"),
            source="/skills",
        ),
    }


@pytest.mark.asyncio
async def test_injects_skills_list(sample_skills):
    """Verify skills list is injected."""
    hook = SkillsVisibilityHook(sample_skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert "<system-reminder" in result.context_injection
    assert "</system-reminder>" in result.context_injection
    assert "python-testing" in result.context_injection
    assert "git-workflow" in result.context_injection
    assert "api-design" in result.context_injection


@pytest.mark.asyncio
async def test_respects_enabled_flag(sample_skills):
    """Verify hook can be disabled."""
    hook = SkillsVisibilityHook(sample_skills, {"enabled": False})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "continue"


@pytest.mark.asyncio
async def test_handles_empty_skills():
    """Verify graceful handling of no skills."""
    hook = SkillsVisibilityHook({}, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "continue"


@pytest.mark.asyncio
async def test_limits_max_visible():
    """Verify max_skills_visible limit."""
    many_skills = {
        f"skill-{i:03d}": SkillMetadata(
            name=f"skill-{i:03d}",
            description=f"Test skill {i}",
            path=Path(f"/skills/skill-{i:03d}/SKILL.md"),
            source="/skills",
        )
        for i in range(100)
    }

    hook = SkillsVisibilityHook(many_skills, {"max_skills_visible": 10})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert "skill-000" in result.context_injection  # Should show first 10
    assert "(90 more" in result.context_injection  # Should show truncation
    assert "skill-050" not in result.context_injection  # Should not show beyond limit


@pytest.mark.asyncio
async def test_xml_boundaries_present(sample_skills):
    """Verify XML boundaries are properly formatted."""
    hook = SkillsVisibilityHook(sample_skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.context_injection is not None
    content = result.context_injection
    assert content.startswith("<system-reminder")
    assert content.endswith("</system-reminder>")
    assert "Available skills (use load_skill tool):" in content


@pytest.mark.asyncio
async def test_configuration_options(sample_skills):
    """Verify configuration options are respected."""
    config = {
        "enabled": True,
        "inject_role": "system",
        "max_skills_visible": 2,
        "ephemeral": False,
        "priority": 15,
    }

    hook = SkillsVisibilityHook(sample_skills, config)
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection_role == "system"
    assert result.ephemeral is False
    assert hook.priority == 15

    # Check that only 2 skills are shown
    assert result.context_injection is not None
    lines = result.context_injection.split("\n")
    skill_lines = [line for line in lines if line.startswith("- **")]
    assert len(skill_lines) == 2


@pytest.mark.asyncio
async def test_default_configuration(sample_skills):
    """Verify default configuration values."""
    hook = SkillsVisibilityHook(sample_skills, {})

    assert hook.enabled is True
    assert hook.inject_role == "system"
    assert hook.max_visible == 50
    assert hook.ephemeral is True
    assert hook.priority == 20


@pytest.mark.asyncio
async def test_skills_sorted_alphabetically(sample_skills):
    """Verify skills are sorted alphabetically."""
    hook = SkillsVisibilityHook(sample_skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.context_injection is not None
    content = result.context_injection
    lines = [line for line in content.split("\n") if line.startswith("- **")]

    # Extract skill names
    skill_names = []
    for line in lines:
        name = line.split("**")[1]
        skill_names.append(name)

    # Verify alphabetical order
    assert skill_names == sorted(skill_names)


@pytest.mark.asyncio
async def test_format_includes_descriptions(sample_skills):
    """Verify skill descriptions are included."""
    hook = SkillsVisibilityHook(sample_skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.context_injection is not None
    content = result.context_injection
    assert "Best practices for Python testing with pytest" in content
    assert "Git branching and commit message standards" in content
    assert "RESTful API design patterns and conventions" in content


@pytest.mark.asyncio
async def test_single_skill():
    """Verify works with single skill."""
    single_skill = {
        "test-skill": SkillMetadata(
            name="test-skill",
            description="A test skill",
            path=Path("/skills/test-skill/SKILL.md"),
            source="/skills",
        )
    }

    hook = SkillsVisibilityHook(single_skill, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert "test-skill" in result.context_injection
    assert "A test skill" in result.context_injection
    # Should not show truncation message for single skill
    assert "more" not in result.context_injection


@pytest.mark.asyncio
async def test_ephemeral_flag_propagates(sample_skills):
    """Verify ephemeral flag is properly set in result."""
    # Test with ephemeral=True (default)
    hook_ephemeral = SkillsVisibilityHook(sample_skills, {"ephemeral": True})
    result_ephemeral = await hook_ephemeral.on_provider_request("provider:request", {})
    assert result_ephemeral.ephemeral is True

    # Test with ephemeral=False
    hook_persistent = SkillsVisibilityHook(sample_skills, {"ephemeral": False})
    result_persistent = await hook_persistent.on_provider_request(
        "provider:request", {}
    )
    assert result_persistent.ephemeral is False


# --- Invocation Control Tests ---


@pytest.mark.asyncio
async def test_disable_model_invocation_skill_in_user_invoked_section():
    """Skills with disable_model_invocation=True must appear in the user-invoked section, not regular section."""
    skills = {
        "visible-skill": SkillMetadata(
            name="visible-skill",
            description="This skill should be visible",
            path=Path("/skills/visible-skill/SKILL.md"),
            source="/skills",
            disable_model_invocation=False,
        ),
        "user-invoked-skill": SkillMetadata(
            name="user-invoked-skill",
            description="This skill should be in user-invoked section",
            path=Path("/skills/user-invoked-skill/SKILL.md"),
            source="/skills",
            disable_model_invocation=True,
        ),
    }

    hook = SkillsVisibilityHook(skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert "visible-skill" in result.context_injection
    # user-invoked skill should be present in the user-invoked section
    assert "user-invoked-skill" in result.context_injection
    assert "User-invoked skills" in result.context_injection


@pytest.mark.asyncio
async def test_shows_skill_without_disable_model_invocation():
    """Skills without disable_model_invocation (default False) are still visible."""
    skills = {
        "normal-skill": SkillMetadata(
            name="normal-skill",
            description="A normal skill with default invocation control",
            path=Path("/skills/normal-skill/SKILL.md"),
            source="/skills",
            # disable_model_invocation defaults to False
        ),
    }

    hook = SkillsVisibilityHook(skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert "normal-skill" in result.context_injection
    assert "A normal skill with default invocation control" in result.context_injection


@pytest.mark.asyncio
async def test_all_skills_disable_model_invocation_shows_user_invoked_section():
    """When all skills have disable_model_invocation=True, hook should return inject_context with user-invoked section."""
    skills = {
        "hidden-1": SkillMetadata(
            name="hidden-1",
            description="First hidden skill",
            path=Path("/skills/hidden-1/SKILL.md"),
            source="/skills",
            disable_model_invocation=True,
        ),
        "hidden-2": SkillMetadata(
            name="hidden-2",
            description="Second hidden skill",
            path=Path("/skills/hidden-2/SKILL.md"),
            source="/skills",
            disable_model_invocation=True,
        ),
    }

    hook = SkillsVisibilityHook(skills, {})
    result = await hook.on_provider_request("provider:request", {})

    # All skills are user-invoked → should still inject context with user-invoked section
    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert "User-invoked skills" in result.context_injection
    assert "hidden-1" in result.context_injection
    assert "hidden-2" in result.context_injection


@pytest.mark.asyncio
async def test_truncation_count_uses_filtered_visible_skills():
    """Truncation count must be based on filtered visible skills, not total skills."""
    # Create 15 visible + 5 hidden skills; max_visible=10
    # Truncation message should say "5 more" (15 - 10), not "10 more" (20 - 10)
    skills = {}
    for i in range(15):
        name = f"visible-{i:03d}"
        skills[name] = SkillMetadata(
            name=name,
            description=f"Visible skill {i}",
            path=Path(f"/skills/{name}/SKILL.md"),
            source="/skills",
            disable_model_invocation=False,
        )
    for i in range(5):
        name = f"hidden-{i:03d}"
        skills[name] = SkillMetadata(
            name=name,
            description=f"Hidden skill {i}",
            path=Path(f"/skills/{name}/SKILL.md"),
            source="/skills",
            disable_model_invocation=True,
        )

    hook = SkillsVisibilityHook(skills, {"max_skills_visible": 10})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    # 15 visible skills with max 10 shown → 5 more remaining
    assert "(5 more" in result.context_injection
    # User-invoked skills appear in their own section
    assert "hidden-000" in result.context_injection
    assert "hidden-001" in result.context_injection
    assert "User-invoked skills" in result.context_injection


# --- Contradiction-free visibility tests ---


@pytest.mark.asyncio
async def test_user_invoked_section_header_is_neutral():
    """User-invoked section header must use neutral text (available via /command)."""
    skills = {
        "cmd-skill": SkillMetadata(
            name="cmd-skill",
            description="A user-invoked command skill",
            path=Path("/skills/cmd-skill/SKILL.md"),
            source="/skills",
            disable_model_invocation=True,
        ),
    }

    hook = SkillsVisibilityHook(skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    content = result.context_injection
    assert "User-invoked skills (available via /command):" in content


@pytest.mark.asyncio
async def test_behavioral_note_not_present():
    """The 'DO NOT mention these skills' behavioral note must be removed entirely."""
    skills = {
        "some-skill": SkillMetadata(
            name="some-skill",
            description="A skill",
            path=Path("/skills/some-skill/SKILL.md"),
            source="/skills",
        ),
    }

    hook = SkillsVisibilityHook(skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    content = result.context_injection
    assert "DO NOT mention" not in content


# --- User-invoked skills section tests ---


@pytest.mark.asyncio
async def test_user_invoked_skills_shown_in_separate_section():
    """Skills with disable_model_invocation=True appear under 'User-invoked skills' heading."""
    skills = {
        "regular-skill": SkillMetadata(
            name="regular-skill",
            description="A regular skill",
            path=Path("/skills/regular-skill/SKILL.md"),
            source="/skills",
            disable_model_invocation=False,
        ),
        "cmd-skill": SkillMetadata(
            name="cmd-skill",
            description="A user-invoked command skill",
            path=Path("/skills/cmd-skill/SKILL.md"),
            source="/skills",
            disable_model_invocation=True,
        ),
    }

    hook = SkillsVisibilityHook(skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    content = result.context_injection
    # Regular skill in available section
    assert "Available skills (use load_skill tool):" in content
    assert "regular-skill" in content
    # User-invoked skill in its own section
    assert "User-invoked skills (available via /command):" in content
    assert "cmd-skill" in content


@pytest.mark.asyncio
async def test_user_invoked_section_not_shown_when_none(sample_skills):
    """When no skills have disable_model_invocation=True, no user-invoked section appears."""
    # sample_skills fixture has no disable_model_invocation=True skills
    hook = SkillsVisibilityHook(sample_skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert "User-invoked skills" not in result.context_injection


@pytest.mark.asyncio
async def test_only_user_invoked_skills_still_injects():
    """When ALL skills have disable_model_invocation=True, hook returns inject_context (not continue)."""
    skills = {
        "only-cmd-skill": SkillMetadata(
            name="only-cmd-skill",
            description="The only skill, and it is user-invoked",
            path=Path("/skills/only-cmd-skill/SKILL.md"),
            source="/skills",
            disable_model_invocation=True,
        ),
    }

    hook = SkillsVisibilityHook(skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert "User-invoked skills" in result.context_injection
    assert "only-cmd-skill" in result.context_injection
    # No regular section since there are no regular skills
    assert "Available skills (use load_skill tool):" not in result.context_injection
