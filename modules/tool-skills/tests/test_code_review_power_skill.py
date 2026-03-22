"""Tests for the /code-review power skill in amplifier-bundle-skills."""

from pathlib import Path

from amplifier_module_tool_skills.discovery import discover_skills, extract_skill_body

# Path to the bundle's skills directory, relative to this test file's location.
# This file is at: amplifier-bundle-skills/modules/tool-skills/tests/test_code_review_power_skill.py
# The skills dir is at: amplifier-bundle-skills/skills/
BUNDLE_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"

CODE_REVIEW_SKILL_PATH = BUNDLE_SKILLS_DIR / "code-review" / "SKILL.md"


def test_code_review_skill_file_exists():
    """SKILL.md file must exist at amplifier-bundle-skills/skills/code-review/SKILL.md."""
    assert CODE_REVIEW_SKILL_PATH.exists(), (
        f"SKILL.md not found at {CODE_REVIEW_SKILL_PATH}"
    )


def test_code_review_skill_is_discoverable():
    """Skill must be discoverable via discover_skills()."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    assert "code-review" in skills, (
        f"'code-review' skill not found via discover_skills(). Found: {list(skills.keys())}"
    )


def test_code_review_skill_context_is_fork():
    """metadata.context must be 'fork'."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    skill = skills["code-review"]
    assert skill.context == "fork", (
        f"Expected context='fork', got context={skill.context!r}"
    )


def test_code_review_skill_disable_model_invocation_is_true():
    """metadata.disable_model_invocation must be True."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    skill = skills["code-review"]
    assert skill.disable_model_invocation is True, (
        f"Expected disable_model_invocation=True, got {skill.disable_model_invocation!r}"
    )


def test_code_review_skill_model_role_is_critique():
    """metadata.model_role must be 'critique'."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    skill = skills["code-review"]
    assert skill.model_role == "critique", (
        f"Expected model_role='critique', got model_role={skill.model_role!r}"
    )


def test_code_review_skill_user_invocable_is_true():
    """metadata.user_invocable must be True."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    skill = skills["code-review"]
    assert skill.user_invocable is True, (
        f"Expected user_invocable=True, got user_invocable={skill.user_invocable!r}"
    )


def test_code_review_skill_body_contains_arguments_placeholder():
    """Body must contain $ARGUMENTS placeholder for optional focus area."""
    body = extract_skill_body(CODE_REVIEW_SKILL_PATH)
    assert body is not None, "Could not extract body from SKILL.md"
    assert "$ARGUMENTS" in body, (
        "Body does not contain '$ARGUMENTS' placeholder for focus area"
    )


def test_code_review_skill_description_mentions_review():
    """Skill description must reference simplification / code review."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    skill = skills["code-review"]
    desc_lower = skill.description.lower()
    assert "simplif" in desc_lower or "review" in desc_lower, (
        f"Description does not mention simplification or review: {skill.description!r}"
    )


def test_code_review_skill_body_describes_parallel_agents():
    """Body must describe spawning parallel review agents."""
    body = extract_skill_body(CODE_REVIEW_SKILL_PATH)
    assert body is not None
    body_lower = body.lower()
    assert "parallel" in body_lower or "agent" in body_lower, (
        "Body does not describe parallel agents"
    )


def test_code_review_skill_body_mentions_git_diff():
    """Body must mention git diff for identifying recently changed files."""
    body = extract_skill_body(CODE_REVIEW_SKILL_PATH)
    assert body is not None
    assert "git diff" in body.lower() or "git" in body.lower(), (
        "Body does not mention git diff for finding changed files"
    )
