"""Tests for the /mass-change power skill in amplifier-bundle-skills."""

import pytest

from pathlib import Path

from amplifier_module_tool_skills.discovery import discover_skills, extract_skill_body

# Path to the bundle's skills directory, relative to this test file's location.
# This file is at: amplifier-bundle-skills/modules/tool-skills/tests/test_mass_change_power_skill.py
# The skills dir is at: amplifier-bundle-skills/skills/
BUNDLE_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"

MASS_CHANGE_SKILL_PATH = BUNDLE_SKILLS_DIR / "mass-change" / "SKILL.md"


@pytest.fixture(scope="module")
def mass_change_skill():
    """Load and return the mass-change skill once per module, avoiding redundant discover_skills() calls."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    return skills.get("mass-change")


def test_mass_change_skill_file_exists():
    """SKILL.md file must exist at amplifier-bundle-skills/skills/mass-change/SKILL.md."""
    assert MASS_CHANGE_SKILL_PATH.exists(), (
        f"SKILL.md not found at {MASS_CHANGE_SKILL_PATH}"
    )


def test_mass_change_skill_is_discoverable():
    """Skill must be discoverable via discover_skills()."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    assert "mass-change" in skills, (
        f"'mass-change' skill not found via discover_skills(). Found: {list(skills.keys())}"
    )


def test_mass_change_skill_context_is_fork(mass_change_skill):
    """metadata.context must be 'fork'."""
    assert mass_change_skill.context == "fork", (
        f"Expected context='fork', got context={mass_change_skill.context!r}"
    )


def test_mass_change_skill_disable_model_invocation_is_true(mass_change_skill):
    """metadata.disable_model_invocation must be True."""
    assert mass_change_skill.disable_model_invocation is True, (
        f"Expected disable_model_invocation=True, got {mass_change_skill.disable_model_invocation!r}"
    )


def test_mass_change_skill_model_role_is_reasoning(mass_change_skill):
    """metadata.model_role must be 'reasoning'."""
    assert mass_change_skill.model_role == "reasoning", (
        f"Expected model_role='reasoning', got model_role={mass_change_skill.model_role!r}"
    )


def test_mass_change_skill_user_invocable_is_true(mass_change_skill):
    """metadata.user_invocable must be True."""
    assert mass_change_skill.user_invocable is True, (
        f"Expected user_invocable=True, got user_invocable={mass_change_skill.user_invocable!r}"
    )


def test_mass_change_skill_body_contains_arguments_placeholder():
    """Body must contain $ARGUMENTS placeholder for change description."""
    body = extract_skill_body(MASS_CHANGE_SKILL_PATH)
    assert body is not None, "Could not extract body from SKILL.md"
    assert "$ARGUMENTS" in body, (
        "Body does not contain '$ARGUMENTS' placeholder for change description"
    )


def test_mass_change_skill_description_mentions_parallel(mass_change_skill):
    """Skill description must reference parallel execution / work units."""
    desc_lower = mass_change_skill.description.lower()
    assert "parallel" in desc_lower or "work unit" in desc_lower, (
        f"Description does not mention parallel execution or work units: {mass_change_skill.description!r}"
    )


def test_mass_change_skill_body_describes_decomposition():
    """Body must describe decomposing change into work units."""
    body = extract_skill_body(MASS_CHANGE_SKILL_PATH)
    assert body is not None
    body_lower = body.lower()
    assert "decompose" in body_lower or "work unit" in body_lower, (
        "Body does not describe decomposing change into work units"
    )


def test_mass_change_skill_body_mentions_delegate_agents():
    """Body must mention delegate agents for parallel execution."""
    body = extract_skill_body(MASS_CHANGE_SKILL_PATH)
    assert body is not None
    body_lower = body.lower()
    assert "delegate" in body_lower or "agent" in body_lower, (
        "Body does not mention delegate agents"
    )


def test_mass_change_skill_body_mentions_git_branches():
    """Body must mention git branches for work units."""
    body = extract_skill_body(MASS_CHANGE_SKILL_PATH)
    assert body is not None
    body_lower = body.lower()
    assert "branch" in body_lower or "mass-change/" in body_lower, (
        "Body does not mention git branches for work units"
    )
