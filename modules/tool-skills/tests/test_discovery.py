"""Tests for skill discovery."""

import os
from pathlib import Path

import pytest
from amplifier_module_tool_skills.discovery import discover_skills
from amplifier_module_tool_skills.discovery import extract_skill_body
from amplifier_module_tool_skills.discovery import parse_skill_frontmatter
from amplifier_module_tool_skills.sources import is_remote_source


def test_parse_skill_frontmatter_valid():
    """Test parsing valid frontmatter."""
    content = """---
name: test-skill
description: Test skill description
version: 1.0.0
---
Body content"""

    test_file = Path("test.md")
    test_file.write_text(content)

    try:
        frontmatter = parse_skill_frontmatter(test_file)
        assert frontmatter is not None
        assert frontmatter["name"] == "test-skill"
        assert frontmatter["description"] == "Test skill description"
        assert frontmatter["version"] == "1.0.0"
    finally:
        test_file.unlink()


def test_parse_skill_frontmatter_no_frontmatter():
    """Test file without frontmatter."""
    content = "Just plain content"

    test_file = Path("test.md")
    test_file.write_text(content)

    try:
        frontmatter = parse_skill_frontmatter(test_file)
        assert frontmatter is None
    finally:
        test_file.unlink()


def test_extract_skill_body():
    """Test extracting markdown body."""
    content = """---
name: test-skill
description: Test
---

# Test Skill

Body content here"""

    test_file = Path("test.md")
    test_file.write_text(content)

    try:
        body = extract_skill_body(test_file)
        assert body is not None
        assert "# Test Skill" in body
        assert "Body content here" in body
        assert "---" not in body
    finally:
        test_file.unlink()


def test_discover_skills_fixture():
    """Test discovering skills from test fixtures."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "skills"

    if not fixtures_dir.exists():
        pytest.skip("Fixtures directory not found")

    skills = discover_skills(fixtures_dir)

    # Should find our example skills
    assert len(skills) >= 1

    # Check that each skill has required fields
    for skill_name, metadata in skills.items():
        assert metadata.name == skill_name
        assert metadata.description
        assert metadata.path.exists()


def test_discover_skills_nonexistent():
    """Test discovering from non-existent directory."""
    skills = discover_skills(Path("/nonexistent/path"))
    assert len(skills) == 0


def test_http_source_rejected():
    """Verify is_remote_source rejects http:// to prevent MITM attacks.

    https:// and git+https:// are accepted as secure remote sources.
    http:// must be rejected (plaintext, vulnerable to MITM).
    Local paths must also return False.
    """
    # Secure remote sources — must be accepted
    assert is_remote_source("https://example.com/skills") is True
    assert is_remote_source("git+https://github.com/org/repo") is True

    # Insecure http:// — must be rejected (MITM risk)
    assert is_remote_source("http://example.com/skills") is False

    # Local paths — must return False
    assert is_remote_source("/local/path/to/skills") is False


def test_discover_skills_through_symlink(tmp_path: Path):
    """Skill directories that are symlinks must be traversed.

    Python 3.13 changed Path.glob() to not follow symlinks by default.
    This test ensures discover_skills() finds skills inside symlinked
    subdirectories on all supported Python versions.

    The canonical location is inside the skills directory to stay within
    the boundary enforced by symlink traversal checking.
    """
    # Create the scan directory
    scan_dir = tmp_path / "skills"
    scan_dir.mkdir()

    # Create the canonical skill location INSIDE the scan directory
    # (boundary-safe symlink: both source and target are within skills/)
    canonical = scan_dir / "canonical" / "my-skill"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: A symlinked skill\n---\nBody\n"
    )

    # Create a symlink within skills/ that points to another location within skills/
    os.symlink(canonical, scan_dir / "my-skill")

    skills = discover_skills(scan_dir)
    assert "my-skill" in skills, (
        f"Skill in symlinked directory not discovered. Found: {list(skills.keys())}"
    )


def test_symlink_outside_boundary_is_skipped(tmp_path: Path):
    """Symlinks that escape the skills directory boundary must not be traversed.

    A symlink like ~/.amplifier/skills/evil -> /etc would index the entire
    /etc tree without boundary checking. This test verifies that discover_skills()
    skips any directory that resolves outside the base skills directory.
    """
    # Create skills base directory with a legitimate skill
    skills_base = tmp_path / "skills"
    skills_base.mkdir()

    legit_skill = skills_base / "legit-skill"
    legit_skill.mkdir()
    (legit_skill / "SKILL.md").write_text(
        "---\nname: legit-skill\ndescription: A legitimate skill\n---\nBody\n"
    )

    # Create an OUTSIDE directory with an evil skill (outside skills_base boundary)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    evil_skill = outside_dir / "evil-skill"
    evil_skill.mkdir()
    (evil_skill / "SKILL.md").write_text(
        "---\nname: evil-skill\ndescription: Should not be discovered\n---\nBody\n"
    )

    # Create a symlink inside skills_base that points to the outside directory
    os.symlink(outside_dir, skills_base / "escape")

    skills = discover_skills(skills_base)

    assert "legit-skill" in skills, (
        f"Legitimate skill was not discovered. Found: {list(skills.keys())}"
    )
    assert "evil-skill" not in skills, (
        f"Evil skill via symlink escape was discovered but should have been blocked. "
        f"Found: {list(skills.keys())}"
    )


# ---------------------------------------------------------------------------
# Tests for git-repo-root boundary (fixes #160)
# ---------------------------------------------------------------------------


def test_symlink_within_repo_root_but_outside_skills_dir_is_allowed(tmp_path: Path):
    """Symlinks that escape the skills dir but stay within the git repo are allowed.

    This is the cross-harness pattern:
        repo-root/
          skills/my-skill/SKILL.md           <- canonical source
          .amplifier/skills/my-skill -> ../../skills/my-skill   <- symlink

    With the git-repo boundary the symlink should be traversed because both the
    symlink and its target live inside the same repository.
    """
    # Simulate a git repo root with a .git marker
    repo_root = tmp_path / "my-repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()  # presence of .git/ is all _find_repo_root needs

    # Canonical skill location — inside repo but OUTSIDE the skills_dir
    canonical = repo_root / "skills" / "my-skill"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: Cross-harness skill\n---\nBody\n"
    )

    # skills_dir is .amplifier/skills/ — the Amplifier scan root
    skills_dir = repo_root / ".amplifier" / "skills"
    skills_dir.mkdir(parents=True)

    # Symlink inside skills_dir pointing to canonical (../.. escapes skills_dir,
    # but the resolved path is still within repo_root)
    os.symlink(canonical, skills_dir / "my-skill")

    skills = discover_skills(skills_dir)
    assert "my-skill" in skills, (
        f"Cross-harness skill via intra-repo symlink was blocked but should be allowed. "
        f"Found: {list(skills.keys())}"
    )


def test_symlink_outside_repo_root_is_blocked(tmp_path: Path):
    """Symlinks that resolve outside the git repository root must be blocked.

    Even when a git repo is detected, symlinks that point entirely outside the
    repo boundary (e.g., pointing to /etc or a sibling directory on the filesystem)
    must not be traversed.
    """
    # Simulate a git repo
    repo_root = tmp_path / "my-repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    skills_dir = repo_root / ".amplifier" / "skills"
    skills_dir.mkdir(parents=True)

    # Canonical skill OUTSIDE the repo root entirely
    outside_root = tmp_path / "outside-repo"
    outside_root.mkdir()
    evil_skill = outside_root / "evil-skill"
    evil_skill.mkdir()
    (evil_skill / "SKILL.md").write_text(
        "---\nname: evil-skill\ndescription: Should not be discovered\n---\nBody\n"
    )

    # Symlink inside skills_dir pointing outside the repo
    os.symlink(outside_root, skills_dir / "escape")

    skills = discover_skills(skills_dir)
    assert "evil-skill" not in skills, (
        f"Skill outside repo root was discovered but should have been blocked. "
        f"Found: {list(skills.keys())}"
    )


def test_non_git_dir_symlink_outside_skills_dir_is_blocked(tmp_path: Path):
    """Non-git directory falls back to strict skills_dir boundary check.

    When there is no git repository, the original strict boundary (skills_dir
    itself) is used, blocking any symlink that resolves outside it.
    """
    # No .git anywhere — tmp_path is the scan root
    skills_base = tmp_path / "skills"
    skills_base.mkdir()

    legit_skill = skills_base / "legit-skill"
    legit_skill.mkdir()
    (legit_skill / "SKILL.md").write_text(
        "---\nname: legit-skill\ndescription: A legitimate skill\n---\nBody\n"
    )

    # Outside directory (no git in sight)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    evil_skill = outside_dir / "evil-skill"
    evil_skill.mkdir()
    (evil_skill / "SKILL.md").write_text(
        "---\nname: evil-skill\ndescription: Should not be discovered\n---\nBody\n"
    )

    os.symlink(outside_dir, skills_base / "escape")

    skills = discover_skills(skills_base)

    assert "legit-skill" in skills, (
        f"Legitimate skill was not discovered. Found: {list(skills.keys())}"
    )
    assert "evil-skill" not in skills, (
        f"Evil skill escaped non-git strict boundary but should be blocked. "
        f"Found: {list(skills.keys())}"
    )
