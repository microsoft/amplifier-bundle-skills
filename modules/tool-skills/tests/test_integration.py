"""Integration test demonstrating skills tool usage."""

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_skills_tool_workflow():
    """
    Integration test showing complete workflow:
    1. List available skills
    2. Get skill info
    3. Load full skill content
    """
    from amplifier_module_tool_skills import SkillsTool

    fixtures_dir = Path(__file__).parent / "fixtures" / "skills"

    if not fixtures_dir.exists():
        pytest.skip("Fixtures directory not found")

    # Create tool
    tool = SkillsTool({"skills_dir": str(fixtures_dir)})

    # Step 1: List all skills
    list_result = await tool.execute({"list": True})
    assert list_result.success
    assert len(list_result.output["skills"]) >= 1

    # Step 2: Get info for first skill
    skill_name = list_result.output["skills"][0]["name"]
    info_result = await tool.execute({"info": skill_name})
    assert info_result.success
    assert info_result.output["name"] == skill_name
    assert "description" in info_result.output

    # Step 3: Load full skill content
    load_result = await tool.execute({"skill_name": skill_name})
    assert load_result.success
    assert "content" in load_result.output
    assert len(load_result.output["content"]) > 100  # Non-trivial content
