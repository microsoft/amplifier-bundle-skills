#!/usr/bin/env python3
"""Standalone extraction of foundation's `skill-description-validation` step.

Source of truth: `amplifier-foundation` `recipes/validate-bundle-repo.yaml`
Phase 2.82 (v3.15.0), step id `skill-description-validation`, read from
`origin/main` at `cfd0e23`. The check body below is a verbatim lift of that
step's Python, with two deliberate differences, both non-behavioural for any
repo whose skills declare a `description`:

  1. It is a file, not a heredoc, and takes `repo_path` as argv[1] rather than
     through `VALIDATE_BUNDLE_REPO_PATH`.
  2. `DESCRIPTION_FIXES["no_description_key"]` carries an equivalent
     remediation sentence, written here. The upstream string was elided by an
     output filter when the recipe was read; it is only ever emitted for a
     SKILL.md that has frontmatter but no `description:` key at all. No skill
     in this repo is in that state, so no run in this lane touches it.

Why extracted at all: this lane's spend authority is $0. The full
`validate-bundle-repo.yaml` recipe runs LLM steps; Phase 2.82 is pure Python
and deterministic, so it is run in isolation for free. Thresholds, exclusion
set, statuses, issue types and messages are unchanged, so the counts it emits
are the counts the recipe emits.

Usage:
    python3 skill_description_check.py <repo_path> [--summary]
"""

import json
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

REPO_PATH = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("VALIDATE_BUNDLE_REPO_PATH", ".")

EXCLUDED_DIRS = {"test-fixtures", "tests", "node_modules", ".git", ".venv"}

SKILL_DESCRIPTION_WARN_CHARS = 400
SKILL_DESCRIPTION_ERROR_CHARS = 800

FRONTMATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n", re.DOTALL)

DESCRIPTION_FIXES = {
    "unreadable": "The file could not be read as UTF-8 text. Fix the encoding or the permissions.",
    "no_frontmatter": "Add a `---` YAML frontmatter block declaring name and description (Agent Skills spec).",
    "no_yaml_module": (
        "PyYAML is not importable in the environment running this recipe, so the description "
        "could not be parsed. Install PyYAML; do not read this as a clean skill."
    ),
    "unparseable_frontmatter": "The frontmatter block is not valid YAML. Fix the YAML syntax.",
    "frontmatter_not_a_mapping": "The frontmatter must be a YAML mapping with `name:` and `description:` keys.",
    "no_description_key": (
        "Add a `description:` key to the frontmatter (see "
        "foundation:context/shared/description-authoring-principles.md)."
    ),
    "description_not_a_string": "`description` must be a string.",
    "description_empty": (
        "`description` is present but empty. Write it (see "
        "foundation:context/shared/description-authoring-principles.md)."
    ),
}

FRONTMATTER_STATUSES = {
    "unreadable",
    "no_frontmatter",
    "no_yaml_module",
    "unparseable_frontmatter",
    "frontmatter_not_a_mapping",
}

results = {
    "phase": "skill_description_validation",
    "excluded_dirs": sorted(EXCLUDED_DIRS),
    "skills_checked": 0,
    "candidates_scanned": 0,
    "errors": [],
    "warnings": [],
    "skill_details": [],
    "thresholds": {
        "warn_chars": SKILL_DESCRIPTION_WARN_CHARS,
        "error_chars": SKILL_DESCRIPTION_ERROR_CHARS,
    },
}


def extract_description(skill_file):
    try:
        content = skill_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "unreadable", ""
    match = FRONTMATTER_RE.match(content)
    if not match:
        return "no_frontmatter", ""
    if yaml is None:
        return "no_yaml_module", ""
    try:
        fm = yaml.safe_load(match.group(1))
    except Exception:
        return "unparseable_frontmatter", ""
    if not isinstance(fm, dict):
        return "frontmatter_not_a_mapping", ""
    if "description" not in fm:
        return "no_description_key", ""
    description = fm.get("description")
    if not isinstance(description, str):
        return "description_not_a_string", ""
    if not description.strip():
        return "description_empty", description
    return "ok", description


path = Path(REPO_PATH).expanduser().resolve()

if not path.exists():
    results["errors"].append(
        {
            "type": "skill_scan_path_error",
            "file": None,
            "severity": "ERROR",
            "message": (
                f"Repository path does not exist: {REPO_PATH} -- no SKILL.md was "
                "scanned. This is a run-ending condition, not a finding that the "
                "repo's skills are clean."
            ),
            "fix": "Check the repo_path context variable passed to this recipe.",
        }
    )
    results["passed"] = False
    results["summary"] = {"skills_checked": 0, "candidates_scanned": 0, "errors": 1, "warnings": 0}
    print(json.dumps(results))
    raise SystemExit(0)

skill_files = []
for f in sorted(path.rglob("SKILL.md")):
    if EXCLUDED_DIRS & set(f.relative_to(path).parts):
        continue
    skill_files.append(f)

for skill_file in skill_files:
    rel_path = skill_file.relative_to(path).as_posix()
    results["candidates_scanned"] += 1
    results["skills_checked"] += 1
    status, description = extract_description(skill_file)
    detail = {"file": rel_path, "description_status": status, "issues": []}

    if status != "ok":
        error_type = (
            "skill_frontmatter_invalid" if status in FRONTMATTER_STATUSES else "skill_description_missing"
        )
        results["errors"].append(
            {
                "type": error_type,
                "file": rel_path,
                "reason": status,
                "severity": "ERROR",
                "message": f"{rel_path}: skill description could not be read ({status}).",
                "fix": DESCRIPTION_FIXES[status],
            }
        )
        detail["issues"].append(error_type)
        detail["description_chars"] = None
        results["skill_details"].append(detail)
        continue

    char_count = len(description)
    detail["description_chars"] = char_count
    detail["description_tokens"] = char_count // 4

    if char_count > SKILL_DESCRIPTION_ERROR_CHARS:
        results["errors"].append(
            {
                "type": "skill_description_excessive",
                "file": rel_path,
                "chars": char_count,
                "severity": "ERROR",
                "message": (
                    f"Skill description in {rel_path} is {char_count} chars "
                    f"(>{SKILL_DESCRIPTION_ERROR_CHARS} threshold, 2x the "
                    f"{SKILL_DESCRIPTION_WARN_CHARS}-char cap -- must shorten)."
                ),
                "fix": (
                    f"Shorten to <={SKILL_DESCRIPTION_WARN_CHARS} chars. See "
                    "foundation:context/shared/description-authoring-principles.md V5, "
                    "or run recipes/refresh-descriptions.yaml for a proposed rewrite "
                    "with a fidelity table."
                ),
            }
        )
        detail["issues"].append("skill_description_excessive")
    elif char_count > SKILL_DESCRIPTION_WARN_CHARS:
        results["warnings"].append(
            {
                "type": "skill_description_high",
                "file": rel_path,
                "chars": char_count,
                "severity": "WARNING",
                "message": (
                    f"Skill description in {rel_path} is {char_count} chars "
                    f"(>{SKILL_DESCRIPTION_WARN_CHARS} cap -- consider trimming)."
                ),
                "fix": (
                    f"Trim toward <={SKILL_DESCRIPTION_WARN_CHARS} chars. See "
                    "foundation:context/shared/description-authoring-principles.md V5."
                ),
            }
        )
        detail["issues"].append("skill_description_high")

    commentary_count = description.lower().count("<commentary>")
    detail["commentary_count"] = commentary_count
    if commentary_count > 0:
        results["errors"].append(
            {
                "type": "commentary_present",
                "file": rel_path,
                "severity": "ERROR",
                "message": (
                    f"{rel_path}: skill description has {commentary_count} "
                    "<commentary> tag(s) -- rejected entirely"
                ),
                "fix": (
                    "Delete <commentary> tags (and the <example> block containing them). "
                    "See description-authoring-principles.md V3."
                ),
            }
        )
        detail["issues"].append("commentary_present")

    example_count = len(re.findall(r"<example>", description, re.IGNORECASE))
    detail["example_count"] = example_count
    if example_count > 0:
        results["errors"].append(
            {
                "type": "example_block_present",
                "file": rel_path,
                "severity": "ERROR",
                "message": (
                    f"{rel_path}: skill description has {example_count} <example> block(s) "
                    "-- example blocks are rejected entirely, not merely capped"
                ),
                "fix": (
                    "Delete all <example> blocks. State the trigger as a decision rule in "
                    "the WHEN clause (V6). See description-authoring-principles.md V3."
                ),
            }
        )
        detail["issues"].append("example_block_present")

    results["skill_details"].append(detail)

if results["candidates_scanned"] == 0:
    results["skipped"] = True
    results["skip_reason"] = "no SKILL.md files found in this repository"

results["passed"] = len(results["errors"]) == 0
results["summary"] = {
    "skills_checked": results["skills_checked"],
    "candidates_scanned": results["candidates_scanned"],
    "errors": len(results["errors"]),
    "warnings": len(results["warnings"]),
}

if "--summary" in sys.argv:
    lengths = sorted(
        d["description_chars"] for d in results["skill_details"] if d.get("description_chars") is not None
    )
    n = len(lengths)
    mean = sum(lengths) / n if n else 0
    median = (
        0
        if not n
        else (lengths[n // 2] if n % 2 else (lengths[n // 2 - 1] + lengths[n // 2]) / 2)
    )
    print(f"skills_checked   {results['skills_checked']}")
    print(f"mean chars       {mean:.0f}")
    print(f"median chars     {median:.0f}")
    print(f"max chars        {max(lengths) if lengths else 0}")
    print(f"over 400 (WARN)  {sum(1 for x in lengths if 400 < x <= 800)}")
    print(f"over 800 (ERROR) {sum(1 for x in lengths if x > 800)}")
    print(f"errors           {len(results['errors'])}")
    print(f"warnings         {len(results['warnings'])}")
else:
    print(json.dumps(results, indent=2))
