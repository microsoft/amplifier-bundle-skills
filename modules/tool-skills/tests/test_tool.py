"""Tests for skills tool."""

from pathlib import Path

import pytest
from amplifier_module_tool_skills import SkillsTool


@pytest.mark.asyncio
async def test_list_skills():
    """Test listing skills."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "skills"

    if not fixtures_dir.exists():
        pytest.skip("Fixtures directory not found")

    tool = SkillsTool({"skills_dir": str(fixtures_dir)})

    result = await tool.execute({"list": True})

    assert result.success
    assert "Available Skills" in result.output["message"]
    assert len(result.output["skills"]) >= 1


@pytest.mark.asyncio
async def test_search_skills():
    """Test searching skills."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "skills"

    if not fixtures_dir.exists():
        pytest.skip("Fixtures directory not found")

    tool = SkillsTool({"skills_dir": str(fixtures_dir)})

    result = await tool.execute({"search": "python"})

    assert result.success
    # Should find python-standards skill
    if "python" in result.output["message"].lower():
        assert len(result.output["matches"]) >= 1


@pytest.mark.asyncio
async def test_load_skill():
    """Test loading a specific skill."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "skills"

    if not fixtures_dir.exists():
        pytest.skip("Fixtures directory not found")

    tool = SkillsTool({"skills_dir": str(fixtures_dir)})

    # First check what skills are available
    list_result = await tool.execute({"list": True})
    if not list_result.output.get("skills"):
        pytest.skip("No skills in fixtures")

    skill_name = list_result.output["skills"][0]["name"]

    # Load the skill
    result = await tool.execute({"skill_name": skill_name})

    assert result.success
    assert "content" in result.output
    assert skill_name in result.output["content"]


@pytest.mark.asyncio
async def test_load_nonexistent_skill():
    """Test loading a skill that doesn't exist."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "skills"
    tool = SkillsTool({"skills_dir": str(fixtures_dir)})

    result = await tool.execute({"skill_name": "nonexistent-skill"})

    assert not result.success
    assert "not found" in result.error["message"].lower()


@pytest.mark.asyncio
async def test_get_skill_info():
    """Test getting skill metadata without loading full content."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "skills"

    if not fixtures_dir.exists():
        pytest.skip("Fixtures directory not found")

    tool = SkillsTool({"skills_dir": str(fixtures_dir)})

    # Get list first
    list_result = await tool.execute({"list": True})
    if not list_result.output.get("skills"):
        pytest.skip("No skills in fixtures")

    skill_name = list_result.output["skills"][0]["name"]

    # Get info
    result = await tool.execute({"info": skill_name})

    assert result.success
    assert result.output["name"] == skill_name
    assert "description" in result.output


@pytest.mark.asyncio
async def test_no_parameters():
    """Test calling tool with no parameters."""
    tool = SkillsTool({"skills_dir": "/nonexistent"})

    result = await tool.execute({})

    assert not result.success
    assert "Must provide" in result.error["message"]
