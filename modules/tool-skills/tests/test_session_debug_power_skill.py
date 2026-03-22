"""Tests for the /session-debug power skill in amplifier-bundle-skills."""

import pytest

from pathlib import Path

from amplifier_module_tool_skills.discovery import discover_skills, extract_skill_body

# Path to the bundle's skills directory, relative to this test file's location.
# This file is at: amplifier-bundle-skills/modules/tool-skills/tests/test_session_debug_power_skill.py
# The skills dir is at: amplifier-bundle-skills/skills/
BUNDLE_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"

SESSION_DEBUG_SKILL_PATH = BUNDLE_SKILLS_DIR / "session-debug" / "SKILL.md"


@pytest.fixture(scope="module")
def session_debug_skill():
    """Load and return the session-debug skill once per module, avoiding redundant discover_skills() calls."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    return skills.get("session-debug")


def test_session_debug_skill_file_exists():
    """SKILL.md file must exist at amplifier-bundle-skills/skills/session-debug/SKILL.md."""
    assert SESSION_DEBUG_SKILL_PATH.exists(), (
        f"SKILL.md not found at {SESSION_DEBUG_SKILL_PATH}"
    )


def test_session_debug_skill_is_discoverable():
    """Skill must be discoverable via discover_skills()."""
    skills = discover_skills(BUNDLE_SKILLS_DIR)
    assert "session-debug" in skills, (
        f"'session-debug' skill not found via discover_skills(). Found: {list(skills.keys())}"
    )


def test_session_debug_skill_context_is_fork(session_debug_skill):
    """metadata.context must be 'fork'."""
    assert session_debug_skill.context == "fork", (
        f"Expected context='fork', got context={session_debug_skill.context!r}"
    )


def test_session_debug_skill_disable_model_invocation_is_true(session_debug_skill):
    """metadata.disable_model_invocation must be True."""
    assert session_debug_skill.disable_model_invocation is True, (
        f"Expected disable_model_invocation=True, got {session_debug_skill.disable_model_invocation!r}"
    )


def test_session_debug_skill_model_role_is_general(session_debug_skill):
    """metadata.model_role must be 'general'."""
    assert session_debug_skill.model_role == "general", (
        f"Expected model_role='general', got model_role={session_debug_skill.model_role!r}"
    )


def test_session_debug_skill_user_invocable_is_true(session_debug_skill):
    """metadata.user_invocable must be True."""
    assert session_debug_skill.user_invocable is True, (
        f"Expected user_invocable=True, got user_invocable={session_debug_skill.user_invocable!r}"
    )


def test_session_debug_skill_body_contains_arguments_placeholder():
    """Body must contain $ARGUMENTS placeholder for specific question."""
    body = extract_skill_body(SESSION_DEBUG_SKILL_PATH)
    assert body is not None, "Could not extract body from SKILL.md"
    assert "$ARGUMENTS" in body, (
        "Body does not contain '$ARGUMENTS' placeholder for specific question"
    )


def test_session_debug_skill_description_mentions_diagnostics(session_debug_skill):
    """Skill description must reference diagnosing or troubleshooting."""
    desc_lower = session_debug_skill.description.lower()
    assert "diagnos" in desc_lower or "troubleshoot" in desc_lower, (
        f"Description does not mention diagnose/diagnostics or troubleshoot: {session_debug_skill.description!r}"
    )


def test_session_debug_skill_body_describes_diagnostic_steps():
    """Body must describe a diagnostic process: delegate to session-analyst, check config, explain findings."""
    body = extract_skill_body(SESSION_DEBUG_SKILL_PATH)
    assert body is not None
    body_lower = body.lower()
    # Should delegate to session-analyst
    assert "session-analyst" in body_lower or "delegate" in body_lower, (
        "Body does not mention delegating to session-analyst"
    )
    # Should mention checking configuration
    assert "configuration" in body_lower or "settings" in body_lower, (
        "Body does not describe checking configuration"
    )
    # Should mention explaining findings
    assert "explain" in body_lower or "plain language" in body_lower, (
        "Body does not describe explaining findings"
    )


def test_session_debug_skill_body_mentions_environment():
    """Body must describe environment diagnostics (env vars, working directory)."""
    body = extract_skill_body(SESSION_DEBUG_SKILL_PATH)
    assert body is not None
    body_lower = body.lower()
    assert "environment" in body_lower or "env" in body_lower, (
        "Body does not mention environment diagnostics"
    )


def test_session_debug_skill_body_mentions_structured_report_sections():
    """Body must reference structured report sections (Environment/Config/Issues/Recommendations)."""
    body = extract_skill_body(SESSION_DEBUG_SKILL_PATH)
    assert body is not None
    body_lower = body.lower()
    # Must mention at least two of the four sections
    sections = ["environment", "configuration", "issues", "recommendation"]
    found = sum(1 for s in sections if s in body_lower)
    assert found >= 2, (
        f"Body does not mention structured report sections. "
        f"Found only {found} of: {sections}"
    )


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
