"""
Test that bundle.md includes the foundation bundle as the first include.
This ensures standalone use (amplifier bundle add git+https://github.com/microsoft/amplifier-bundle-skills@main)
provides a complete working session with foundation tools, and @foundation: @-mentions resolve correctly.
"""
import re
from pathlib import Path


BUNDLE_MD_PATH = Path(__file__).parent.parent / "bundle.md"
FOUNDATION_INCLUDE = "bundle: git+https://github.com/microsoft/amplifier-foundation@main"
SKILLS_INCLUDE = "bundle: skills:behaviors/skills"


def read_bundle_md() -> str:
    return BUNDLE_MD_PATH.read_text()


def parse_includes_from_frontmatter(content: str) -> list[str]:
    """Extract the includes list from the YAML frontmatter."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return []
    frontmatter = match.group(1)

    includes_match = re.search(r"^includes:\n((?:  - .+\n?)+)", frontmatter, re.MULTILINE)
    if not includes_match:
        return []

    includes_block = includes_match.group(1)
    includes = re.findall(r"  - (.+)", includes_block)
    return includes


def test_foundation_include_present():
    """foundation bundle should be in the includes list."""
    content = read_bundle_md()
    includes = parse_includes_from_frontmatter(content)
    assert any(FOUNDATION_INCLUDE in inc for inc in includes), (
        f"Expected to find '{FOUNDATION_INCLUDE}' in includes, but got: {includes}"
    )


def test_foundation_include_is_first():
    """foundation bundle should be the FIRST include (before skills behavior)."""
    content = read_bundle_md()
    includes = parse_includes_from_frontmatter(content)
    assert len(includes) >= 2, f"Expected at least 2 includes, got: {includes}"
    assert FOUNDATION_INCLUDE in includes[0], (
        f"Expected foundation bundle as first include, but first was: {includes[0]}"
    )


def test_skills_include_still_present():
    """skills behavior include should still be present after foundation include."""
    content = read_bundle_md()
    includes = parse_includes_from_frontmatter(content)
    assert any(SKILLS_INCLUDE in inc for inc in includes), (
        f"Expected to find '{SKILLS_INCLUDE}' in includes, but got: {includes}"
    )


def test_foundation_comes_before_skills():
    """foundation bundle include must appear before skills behavior include."""
    content = read_bundle_md()
    includes = parse_includes_from_frontmatter(content)

    foundation_idx = next(
        (i for i, inc in enumerate(includes) if FOUNDATION_INCLUDE in inc), None
    )
    skills_idx = next(
        (i for i, inc in enumerate(includes) if SKILLS_INCLUDE in inc), None
    )

    assert foundation_idx is not None, f"Foundation include not found in: {includes}"
    assert skills_idx is not None, f"Skills include not found in: {includes}"
    assert foundation_idx < skills_idx, (
        f"Foundation (idx={foundation_idx}) must come before skills (idx={skills_idx})"
    )
