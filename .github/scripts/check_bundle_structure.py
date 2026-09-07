#!/usr/bin/env python3
"""Cheap structural check for this bundle: does its YAML actually parse?

Run it exactly the same way CI does::

    uv run --no-project --with pyyaml python .github/scripts/check_bundle_structure.py

What it checks, and nothing more:

1. ``bundle.md`` has a ``---`` fenced YAML frontmatter block that parses, and
   declares ``bundle.name`` and ``bundle.version``.
2. Every LOCAL entry in the frontmatter's ``includes:`` list resolves to a file
   that exists on disk. Remote includes (``git+https://...``) are reported and
   skipped -- resolving them would need the network.
3. Every ``behaviors/*.yaml`` parses as YAML and is a non-empty mapping.
4. Every ``skills/*/SKILL.md`` has parseable frontmatter declaring ``name`` and
   ``description``. This is the payload of a SKILLS bundle: a skill whose
   frontmatter does not parse is invisible at runtime, and nothing else in this
   repo notices.

Deliberate design notes:

* An EMPTY glob is a FAILURE, not a pass. A check that silently returns "0
  problems found in 0 files" is indistinguishable from a working one.
* Paths are resolved relative to this file's own location and reported with
  ``as_posix()`` so the output reads the same on every OS.
* No network, no API keys, no LLM. Runs in about a second.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

problems: list[str] = []
checked: list[str] = []


def rel(path: Path) -> str:
    """Repo-relative, forward-slash path -- identical output on every OS."""
    return path.relative_to(REPO_ROOT).as_posix()


def parse_frontmatter(text: str) -> dict | None:
    """Return the parsed YAML frontmatter of a markdown file, or None if malformed."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return None
    loaded = yaml.safe_load("\n".join(lines[1:end]))
    return loaded if isinstance(loaded, dict) else None


def resolve_include(reference: str) -> Path | None:
    """Resolve a local ``<bundle-name>:<relative/path>`` include to a file on disk.

    A behavior reference carries no extension (``skills:behaviors/skills``), so
    the bare path and the ``.yaml`` / ``.yml`` / ``.md`` forms are all tried.
    """
    _, _, relative = reference.partition(":")
    relative = relative or reference
    base = REPO_ROOT / relative
    for candidate in (base, base.with_suffix(".yaml"), base.with_suffix(".yml"), base.with_suffix(".md")):
        if candidate.is_file():
            return candidate
    return None


# --- 1 + 2: bundle.md frontmatter -------------------------------------------

bundle_md = REPO_ROOT / "bundle.md"
remote_includes = 0
local_includes = 0

if not bundle_md.is_file():
    problems.append("bundle.md is missing from the repository root")
else:
    try:
        parsed = parse_frontmatter(bundle_md.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        parsed = None
        problems.append(f"{rel(bundle_md)}: frontmatter is not valid YAML: {exc}")

    if parsed is None:
        problems.append(f"{rel(bundle_md)}: no parseable '---' fenced YAML frontmatter mapping")
    else:
        checked.append(rel(bundle_md))
        bundle_block = parsed.get("bundle")
        if not isinstance(bundle_block, dict):
            problems.append(f"{rel(bundle_md)}: frontmatter has no 'bundle:' mapping")
        else:
            for key in ("name", "version"):
                if not bundle_block.get(key):
                    problems.append(f"{rel(bundle_md)}: frontmatter is missing 'bundle.{key}'")

        includes = parsed.get("includes") or []
        if not isinstance(includes, list):
            problems.append(f"{rel(bundle_md)}: 'includes:' must be a list, got {type(includes).__name__}")
            includes = []
        if not includes:
            problems.append(f"{rel(bundle_md)}: 'includes:' is empty -- nothing was actually checked")
        for entry in includes:
            # Entries are mappings of one key, e.g. `- bundle: skills:behaviors/skills`.
            reference = entry.get("bundle") if isinstance(entry, dict) else entry
            if not isinstance(reference, str):
                problems.append(f"{rel(bundle_md)}: includes entry is not a bundle reference: {entry!r}")
                continue
            if reference.startswith(("git+", "http://", "https://")):
                remote_includes += 1
                continue
            local_includes += 1
            if resolve_include(reference) is None:
                problems.append(f"{rel(bundle_md)}: includes '{reference}' -> no such file in this repo")


# --- 3: behaviors/*.yaml -----------------------------------------------------


def parse_all_yaml(directory: str, pattern: str) -> int:
    """Parse every match as a YAML mapping; return how many files were found."""
    root = REPO_ROOT / directory
    if not root.is_dir():
        problems.append(f"{directory}/ directory is missing")
        return 0

    matches = sorted(root.glob(pattern))
    if not matches:
        # An empty glob is a failure. See the module docstring.
        problems.append(f"{directory}/{pattern} matched NO files -- nothing was actually checked")
        return 0

    for path in matches:
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            problems.append(f"{rel(path)}: not valid YAML: {exc}")
            continue
        if not isinstance(loaded, dict) or not loaded:
            problems.append(f"{rel(path)}: expected a non-empty YAML mapping, got {type(loaded).__name__}")
            continue
        checked.append(rel(path))
    return len(matches)


behaviors_count = parse_all_yaml("behaviors", "*.yaml")


# --- 4: skills/*/SKILL.md frontmatter ---------------------------------------

skills_root = REPO_ROOT / "skills"
skill_files = sorted(skills_root.glob("*/SKILL.md")) if skills_root.is_dir() else []

if not skills_root.is_dir():
    problems.append("skills/ directory is missing")
elif not skill_files:
    problems.append("skills/*/SKILL.md matched NO files -- nothing was actually checked")
else:
    # A skill directory with no SKILL.md ships nothing; catch it explicitly
    # rather than letting the glob quietly shrink.
    for directory in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        if not (directory / "SKILL.md").is_file():
            problems.append(f"{rel(directory)}/: skill directory has no SKILL.md")

    for path in skill_files:
        try:
            parsed_skill = parse_frontmatter(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            problems.append(f"{rel(path)}: frontmatter is not valid YAML: {exc}")
            continue
        if parsed_skill is None:
            problems.append(f"{rel(path)}: no parseable '---' fenced YAML frontmatter mapping")
            continue
        for key in ("name", "description"):
            if not parsed_skill.get(key):
                problems.append(f"{rel(path)}: frontmatter is missing '{key}'")
        checked.append(rel(path))


# --- report ------------------------------------------------------------------

print(f"bundle.md frontmatter : {'ok' if bundle_md.is_file() else 'MISSING'}")
print(f"bundle.md includes    : {local_includes} local, {remote_includes} remote (not resolved)")
print(f"behaviors/*.yaml      : {behaviors_count} file(s)")
print(f"skills/*/SKILL.md     : {len(skill_files)} file(s)")
print(f"parsed cleanly        : {len(checked)} file(s)")

if problems:
    print(f"\nFAIL -- {len(problems)} problem(s):", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    sys.exit(1)

print("\nOK -- bundle structure checks passed")
