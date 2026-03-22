"""Tests for the /skills-assist power skill in amplifier-bundle-skills."""

import pytest

from pathlib import Path

from amplifier_module_tool_skills.discovery import discover_skills, extract_skill_body

# Path to the bundle's skills directory, relative to this test file's location.
# This file is at: amplifier-bundle-skills/modules/tool-skills/tests/test_skills_assist_power_skill.py
# The skills dir is at: amplifier-bundle-skills/skills/
BUNDLE_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"

SKILLS_ASSIST_SKILL_PATH = BUNDLE_SKILLS_DIR / "skills-assist" / "SKILL.md"


@pytest.fixture(scope="module")
def skills_assist_skill():
    """Load and return the skills-assist skill once per module, avoiding redundant discover_skills() calls."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    return skills.get("skills-assist")


def test_skills_assist_skill_file_exists():
    """SKILL.md file must exist at amplifier-bundle-skills/skills/skills-assist/SKILL.md."""
    assert SKILLS_ASSIST_SKILL_PATH.exists(), (
        f"SKILL.md not found at {SKILLS_ASSIST_SKILL_PATH}"
    )


def test_skills_assist_skill_is_discoverable():
    """Skill must be discoverable via discover_skills()."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    assert "skills-assist" in skills, (
        f"'skills-assist' skill not found via discover_skills(). Found: {list(skills.keys())}"
    )


def test_skills_assist_skill_context_is_fork(skills_assist_skill):
    """metadata.context must be 'fork'."""
    assert skills_assist_skill.context == "fork", (
        f"Expected context='fork', got context={skills_assist_skill.context!r}"
    )


def test_skills_assist_skill_disable_model_invocation_is_false(skills_assist_skill):
    """metadata.disable_model_invocation must be False."""
    assert skills_assist_skill.disable_model_invocation is False, (
        f"Expected disable_model_invocation=False, got {skills_assist_skill.disable_model_invocation!r}"
    )


def test_skills_assist_skill_model_role_is_general(skills_assist_skill):
    """metadata.model_role must be 'general'."""
    assert skills_assist_skill.model_role == "general", (
        f"Expected model_role='general', got model_role={skills_assist_skill.model_role!r}"
    )


def test_skills_assist_skill_user_invocable_is_true(skills_assist_skill):
    """metadata.user_invocable must be True."""
    assert skills_assist_skill.user_invocable is True, (
        f"Expected user_invocable=True, got user_invocable={skills_assist_skill.user_invocable!r}"
    )


def test_skills_assist_skill_description_mentions_skills(skills_assist_skill):
    """Skill description must reference 'skill'."""
    desc_lower = skills_assist_skill.description.lower()
    assert "skill" in desc_lower, (
        f"Description does not mention 'skill': {skills_assist_skill.description!r}"
    )


def test_skills_assist_skill_body_contains_arguments_placeholder():
    """Body must contain $ARGUMENTS placeholder for user question."""
    body = extract_skill_body(SKILLS_ASSIST_SKILL_PATH)
    assert body is not None, "Could not extract body from SKILL.md"
    assert "$ARGUMENTS" in body, (
        "Body does not contain '$ARGUMENTS' placeholder for user question"
    )


def test_skills_assist_skill_body_references_companion_files():
    """Body must reference companion files via authoring-guide.md, companion, or read_file."""
    body = extract_skill_body(SKILLS_ASSIST_SKILL_PATH)
    assert body is not None, "Could not extract body from SKILL.md"
    assert (
        "authoring-guide.md" in body
        or "companion" in body.lower()
        or "read_file" in body
    ), (
        "Body does not reference companion files (authoring-guide.md, companion, or read_file)"
    )


def test_skills_assist_companion_files_exist():
    """All 4 companion reference files must exist alongside SKILL.md."""
    companion_dir = SKILLS_ASSIST_SKILL_PATH.parent
    expected_files = [
        "authoring-guide.md",
        "spec-reference.md",
        "compatibility-matrix.md",
        "skills-vs-agents.md",
    ]
    missing = [f for f in expected_files if not (companion_dir / f).exists()]
    assert not missing, f"Missing companion files in {companion_dir}: {missing}"


def test_all_five_skills_discoverable_together():
    """All 5 skills (image-vision + code-review + mass-change + session-debug + skills-assist) must be discoverable together."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    expected_skills = {
        "image-vision",
        "code-review",
        "mass-change",
        "session-debug",
        "skills-assist",
    }
    missing = expected_skills - set(skills.keys())
    assert not missing, f"Missing skills: {missing}. Found: {list(skills.keys())}"
