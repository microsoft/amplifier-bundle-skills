"""Tests for multi-source skill discovery."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from amplifier_module_tool_skills.discovery import discover_skills_multi_source
from amplifier_module_tool_skills.discovery import get_default_skills_dirs


def test_multi_source_priority():
    """Test that multi-source discovery follows priority order."""
    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create two directories with overlapping skills
        dir1 = tmppath / "source1"
        dir2 = tmppath / "source2"
        dir1.mkdir()
        dir2.mkdir()

        # Create same skill in both directories
        (dir1 / "test-skill").mkdir()
        (dir1 / "test-skill" / "SKILL.md").write_text(
            """---
name: test-skill
description: From source 1
version: 1.0.0
---
Content from source 1"""
        )

        (dir2 / "test-skill").mkdir()
        (dir2 / "test-skill" / "SKILL.md").write_text(
            """---
name: test-skill
description: From source 2
version: 2.0.0
---
Content from source 2"""
        )

        # Discover with priority: dir1 > dir2
        skills = discover_skills_multi_source([dir1, dir2])

        # Should get skill from dir1 (higher priority)
        assert len(skills) == 1
        assert skills["test-skill"].description == "From source 1"
        assert skills["test-skill"].version == "1.0.0"


def test_multi_source_merge():
    """Test that skills from different sources are merged."""
    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create two directories with different skills
        dir1 = tmppath / "source1"
        dir2 = tmppath / "source2"
        dir1.mkdir()
        dir2.mkdir()

        # Create skill1 in dir1
        (dir1 / "skill1").mkdir()
        (dir1 / "skill1" / "SKILL.md").write_text(
            """---
name: skill1
description: Skill from source 1
---
Content 1"""
        )

        # Create skill2 in dir2
        (dir2 / "skill2").mkdir()
        (dir2 / "skill2" / "SKILL.md").write_text(
            """---
name: skill2
description: Skill from source 2
---
Content 2"""
        )

        # Discover from both
        skills = discover_skills_multi_source([dir1, dir2])

        # Should have both skills
        assert len(skills) == 2
        assert "skill1" in skills
        assert "skill2" in skills


def test_get_default_skills_dirs():
    """Test default skills directory search paths."""
    dirs = get_default_skills_dirs()

    # Should have at least workspace and user paths
    assert len(dirs) >= 2

    # Check expected paths
    path_strs = [str(d) for d in dirs]
    assert any(".amplifier/skills" in p for p in path_strs)
    assert any(".amplifier/skills" in p for p in path_strs)


def test_multi_source_nonexistent_dirs():
    """Test multi-source with some non-existent directories."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "skills"

    if not fixtures_dir.exists():
        pytest.skip("Fixtures directory not found")

    # Mix existing and non-existent
    skills = discover_skills_multi_source([Path("/nonexistent1"), fixtures_dir, Path("/nonexistent2")])

    # Should still find skills from the existing directory
    assert len(skills) >= 1
