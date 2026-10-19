"""A skill added to a configured directory after mount is found on first use."""

from pathlib import Path

import pytest
from amplifier_module_tool_skills import SkillsDiscovery
from amplifier_module_tool_skills import SkillsTool


def _write_skill(root: Path, name: str, body: str = "Body text.") -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: The {name} skill.\n---\n\n{body}\n"
    )


@pytest.mark.asyncio
async def test_load_finds_skill_added_after_mount(tmp_path):
    _write_skill(tmp_path, "early-skill")
    tool = SkillsTool({"skills_dir": str(tmp_path)})
    discovery = SkillsDiscovery(tool.skills)
    assert "late-skill" not in tool.skills

    _write_skill(tmp_path, "late-skill", body="Late body.")
    result = await tool.execute({"skill_name": "late-skill"})

    assert result.success
    assert "Late body." in result.output["content"]
    # The shared catalog sees the new skill without a second miss.
    assert discovery.find("late-skill") is not None


@pytest.mark.asyncio
async def test_info_finds_skill_added_after_mount(tmp_path):
    _write_skill(tmp_path, "early-skill")
    tool = SkillsTool({"skills_dir": str(tmp_path)})

    _write_skill(tmp_path, "late-skill")
    result = await tool.execute({"info": "late-skill"})

    assert result.success
    assert result.output["name"] == "late-skill"


@pytest.mark.asyncio
async def test_rescan_keeps_existing_entries(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_skill(first, "early-skill")
    tool = SkillsTool({"skills_dirs": [str(first), str(second)]})
    original = tool.skills["early-skill"]

    _write_skill(second, "early-skill", body="Shadowed.")
    result = await tool.execute({"skill_name": "missing-skill"})

    assert not result.success
    assert "not found" in result.error["message"].lower()
    assert tool.skills["early-skill"] is original


@pytest.mark.asyncio
async def test_miss_lists_skills_found_by_the_rescan(tmp_path):
    _write_skill(tmp_path, "early-skill")
    tool = SkillsTool({"skills_dir": str(tmp_path)})

    _write_skill(tmp_path, "late-skill")
    result = await tool.execute({"skill_name": "missing-skill"})

    assert not result.success
    assert "late-skill" in result.error["message"]
