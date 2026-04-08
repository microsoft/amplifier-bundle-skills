"""Tests that SKILL.md has correct structure after output-density and skills-assist updates."""

import re
from pathlib import Path

SKILL_MD = Path(__file__).parent / "SKILL.md"


def _read_skill() -> str:
    return SKILL_MD.read_text()


class TestStepNumbering:
    """Steps must be numbered 1-6 in the correct order."""

    def test_six_steps_in_order(self):
        content = _read_skill()
        headings = re.findall(r"^### (\d+)\. (.+)$", content, re.MULTILINE)
        assert len(headings) == 6, f"Expected 6 steps, got {len(headings)}: {headings}"
        numbers = [int(h[0]) for h in headings]
        assert numbers == [1, 2, 3, 4, 5, 6]

    def test_step_names(self):
        content = _read_skill()
        headings = re.findall(r"^### \d+\. (.+)$", content, re.MULTILINE)
        expected = [
            "Consult Skills-Assist",
            "Analyze the Session",
            "Interview the User",
            "Write the SKILL.md",
            "Test the Skill",
            "Review and Save",
        ]
        assert headings == expected, (
            f"Step names don't match.\nExpected: {expected}\nGot: {headings}"
        )


class TestConsultSkillsAssist:
    """Step 1 must require consulting skills-assist."""

    def test_load_skill_call_present(self):
        content = _read_skill()
        assert 'load_skill("skills-assist")' in content

    def test_skills_assist_is_source_of_truth(self):
        content = _read_skill()
        assert "skills-assist is the source of truth" in content

    def test_examples_are_illustrative(self):
        content = _read_skill()
        assert "illustrative samples" in content


class TestOutputDensity:
    """Step 3 (Interview) must contain output-density guidance."""

    def test_output_density_rule_present(self):
        content = _read_skill()
        assert "Output density rule:" in content

    def test_density_guidance_before_rounds(self):
        content = _read_skill()
        density_pos = content.index("Output density rule:")
        round1_pos = content.index("#### Round 1:")
        assert density_pos < round1_pos, (
            "Output density rule must appear before Round 1"
        )

    def test_density_in_interview_step(self):
        content = _read_skill()
        # Output density should be between Step 3 heading and Step 4 heading
        step3_pos = content.index("### 3. Interview the User")
        step4_pos = content.index("### 4. Write the SKILL.md")
        density_pos = content.index("Output density rule:")
        assert step3_pos < density_pos < step4_pos


class TestSoftenedConventions:
    """Step 4 (Write) must soften hardcoded conventions."""

    def test_template_has_consult_qualifier(self):
        content = _read_skill()
        assert (
            "Consult skills-assist for the full set of available frontmatter fields"
            in content
        )

    def test_frontmatter_rules_heading_softened(self):
        content = _read_skill()
        assert "Frontmatter rules (key examples" in content
        assert "consult skills-assist for complete reference" in content

    def test_step_annotations_heading_softened(self):
        content = _read_skill()
        assert "Step annotations (key examples" in content
        assert "consult skills-assist for complete conventions" in content


class TestTestingStep:
    """Step 5 must contain testing instructions."""

    def test_testing_step_exists(self):
        content = _read_skill()
        assert "### 5. Test the Skill" in content

    def test_load_skill_verification(self):
        content = _read_skill()
        # Find the testing step content
        step5_pos = content.index("### 5. Test the Skill")
        step6_pos = content.index("### 6. Review and Save")
        testing_content = content[step5_pos:step6_pos]
        assert "load_skill" in testing_content
        assert "loads without errors" in testing_content

    def test_success_criteria_on_testing_step(self):
        content = _read_skill()
        step5_pos = content.index("### 5. Test the Skill")
        step6_pos = content.index("### 6. Review and Save")
        testing_content = content[step5_pos:step6_pos]
        assert "**Success criteria**:" in testing_content
