"""
Test that .gitignore exists at the bundle root with all required patterns.
This ensures generated Python files, caches, and build artifacts are excluded from git.
"""

from pathlib import Path


GITIGNORE_PATH = Path(__file__).parent.parent / ".gitignore"

REQUIRED_PATTERNS = [
    "__pycache__/",
    "*.pyc",
    ".venv/",
    ".pytest_cache/",
    ".ruff_cache/",
    "*.egg-info/",
    "dist/",
    "build/",
    ".DS_Store",
]


def test_gitignore_exists():
    """The .gitignore file must exist at the bundle root."""
    assert GITIGNORE_PATH.exists(), (
        f"Expected .gitignore at {GITIGNORE_PATH} but it does not exist"
    )


def test_gitignore_has_all_required_patterns():
    """The .gitignore must contain all 9 required patterns."""
    assert GITIGNORE_PATH.exists(), ".gitignore does not exist"
    content = GITIGNORE_PATH.read_text()
    lines = [line.strip() for line in content.splitlines()]
    missing = [pattern for pattern in REQUIRED_PATTERNS if pattern not in lines]
    assert not missing, (
        f"The following required patterns are missing from .gitignore: {missing}"
    )


def test_gitignore_has_exactly_nine_patterns():
    """The .gitignore must contain exactly 9 patterns (no more, no less)."""
    assert GITIGNORE_PATH.exists(), ".gitignore does not exist"
    content = GITIGNORE_PATH.read_text()
    non_empty_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert len(non_empty_lines) == 9, (
        f"Expected exactly 9 patterns, but found {len(non_empty_lines)}: {non_empty_lines}"
    )
