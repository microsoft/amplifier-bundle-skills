"""
Test that the adapt-skill SKILL.md exists and conforms to required structure.

Validates frontmatter fields, required steps, and key content expectations
for the adapt-skill skill that ports skills from other platforms to Amplifier.
"""

import re
from pathlib import Path


SKILL_MD_PATH = Path(__file__).parent.parent / "skills" / "adapt-skill" / "SKILL.md"


def read_skill_md() -> str:
    assert SKILL_MD_PATH.exists(), (
        f"Expected SKILL.md at {SKILL_MD_PATH} but it does not exist"
    )
    return SKILL_MD_PATH.read_text()


def parse_frontmatter(content: str) -> str:
    """Extract raw frontmatter from SKILL.md."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    assert match, "SKILL.md must have YAML frontmatter delimited by ---"
    return match.group(1)


# --- Existence ---


def test_skill_md_exists():
    """The adapt-skill SKILL.md must exist."""
    assert SKILL_MD_PATH.exists(), (
        f"Expected SKILL.md at {SKILL_MD_PATH} but it does not exist"
    )


# --- Frontmatter fields ---


def test_frontmatter_name():
    """Frontmatter must have name: adapt-skill."""
    fm = parse_frontmatter(read_skill_md())
    assert re.search(r"^name:\s*adapt-skill\s*$", fm, re.MULTILINE), (
        "Frontmatter must contain 'name: adapt-skill'"
    )


def test_frontmatter_user_invocable():
    """Frontmatter must have user-invocable: true."""
    fm = parse_frontmatter(read_skill_md())
    assert re.search(r"^user-invocable:\s*true\s*$", fm, re.MULTILINE), (
        "Frontmatter must contain 'user-invocable: true'"
    )


def test_frontmatter_model_role():
    """Frontmatter must have model_role: general."""
    fm = parse_frontmatter(read_skill_md())
    assert re.search(r"^model_role:\s*general\s*$", fm, re.MULTILINE), (
        "Frontmatter must contain 'model_role: general'"
    )


def test_frontmatter_allowed_tools_includes_delegate():
    """allowed-tools must include delegate (for skills-assist and foundation:explorer)."""
    fm = parse_frontmatter(read_skill_md())
    assert "delegate" in fm, (
        "allowed-tools must include 'delegate' for skills-assist consultation"
    )


def test_frontmatter_description_has_trigger_phrases():
    """Description must include trigger phrases for model routing."""
    fm = parse_frontmatter(read_skill_md())
    for phrase in ["adapt a skill", "port a skill", "convert a skill"]:
        assert phrase in fm.lower(), (
            f"Description should contain trigger phrase: '{phrase}'"
        )


# --- No context: fork (inline skill) ---


def test_no_context_fork():
    """Skill must be inline (no context: fork) since it needs multi-round interaction."""
    fm = parse_frontmatter(read_skill_md())
    assert "context:" not in fm, (
        "adapt-skill must be inline (no 'context:' field) — it requires "
        "multi-round user interaction which forked skills cannot do"
    )


def test_no_disable_model_invocation():
    """Skill must be model-invocable (no disable-model-invocation)."""
    fm = parse_frontmatter(read_skill_md())
    assert "disable-model-invocation" not in fm, (
        "adapt-skill must not have disable-model-invocation — "
        "it should trigger on natural phrases"
    )


# --- Required steps ---


REQUIRED_STEPS = [
    ("1", "Consult Skills-Assist"),
    ("2", "Explore the Target Bundle"),
    ("3", "Read and Analyze the Source Skill"),
    ("4", "Research Source Platform Conventions"),
    ("5", "Design the Adapted Skill"),
    ("6", "Write the SKILL.md"),
    ("7", "Test the Skill"),
    ("8", "Save, Commit, and Push"),
]


def test_all_required_steps_present():
    """All 8 required steps must be present as ### headings."""
    content = read_skill_md()
    for step_num, step_name in REQUIRED_STEPS:
        pattern = rf"###\s+{step_num}\.\s+{re.escape(step_name)}"
        assert re.search(pattern, content), (
            f"Missing required step: ### {step_num}. {step_name}"
        )


# --- Key content: skills-assist delegation ---


def test_skills_assist_consultation_in_step_1():
    """Step 1 must instruct loading skills-assist as source of truth."""
    content = read_skill_md()
    assert 'load_skill("skills-assist")' in content, (
        'Step 1 must include load_skill("skills-assist") instruction'
    )


# --- Key content: testing step ---


def test_testing_step_includes_delegate_self():
    """Step 7 (Test) must include delegate(agent=\"self\") for test session."""
    content = read_skill_md()
    assert 'delegate(agent="self"' in content, (
        'Testing step must include delegate(agent="self") for spawning test session'
    )


def test_testing_step_includes_load_skill():
    """Step 7 (Test) must verify the skill loads via load_skill."""
    content = read_skill_md()
    # Find the testing section
    test_section = re.search(
        r"###\s+7\.\s+Test the Skill(.*?)(?=###|\Z)", content, re.DOTALL
    )
    assert test_section, "Step 7 (Test the Skill) section not found"
    section_content = test_section.group(1)
    assert "load_skill" in section_content, (
        "Testing step must include load_skill verification"
    )


# --- Success criteria on every step ---


def test_every_step_has_success_criteria():
    """Every step must end with **Success criteria** block."""
    content = read_skill_md()
    for step_num, step_name in REQUIRED_STEPS:
        # Extract each step section
        pattern = rf"(###\s+{step_num}\.\s+{re.escape(step_name)}.*?)(?=###\s+\d|\Z)"
        section = re.search(pattern, content, re.DOTALL)
        assert section, f"Could not find section for step {step_num}"
        assert "**Success criteria**" in section.group(1), (
            f"Step {step_num} ({step_name}) must have **Success criteria** block"
        )
