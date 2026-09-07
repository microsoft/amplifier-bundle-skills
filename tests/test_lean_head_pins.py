"""Pins for the lean always-on head.

`context/skills-instructions.md` and the `load_skill` tool description are both
`context.include` / tool-schema content: they are paid for on EVERY request of EVERY
session, whether or not a skill is ever loaded. They were compressed by measurement
(model_performance-smy5, applying the patches measured in zc6t / amplifier-foundation
PR #372) from 4,478 -> 1,993 and 1,647 -> 968 characters, with the full-head effect
measured at -13.57% $/task, CI [-22.27%, -4.86%].

These tests make drift-back LOUD. They pin three things per target:

1. A size ceiling -- prose cannot creep back toward the stock length.
2. Every rule / constraint / command / pointer that must survive.
3. The removed stock prose, which must NOT reappear verbatim.

A legitimate future edit is still free to change wording; it just cannot silently
restore the long form or drop a rule.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).parent.parent
CONTEXT_FILE = REPO / "context" / "skills-instructions.md"
TOOL_MODULE = REPO / "modules" / "tool-skills" / "amplifier_module_tool_skills" / "__init__.py"

# Measured at application time. Ceilings sit ~15% above the pinned value so a small
# honest edit passes while a drift back toward stock (4,478 / 1,647) fails.
CONTEXT_CHARS_AT_PIN = 1993
CONTEXT_CHARS_CEILING = 2300
CONTEXT_CHARS_STOCK = 4478

LOAD_SKILL_CHARS_AT_PIN = 968
LOAD_SKILL_CHARS_CEILING = 1150
LOAD_SKILL_CHARS_STOCK = 1647


def read_context() -> str:
    return CONTEXT_FILE.read_text(encoding="utf-8")


def read_load_skill_description() -> str:
    src = TOOL_MODULE.read_text(encoding="utf-8")
    match = re.search(r'    name = "load_skill"\n    description = """(.*?)"""\n', src, re.S)
    assert match, "load_skill description block not found in tool-skills module"
    return match.group(1)


# --------------------------------------------------------------------------------------
# context/skills-instructions.md
# --------------------------------------------------------------------------------------

CONTEXT_REQUIRED = [
    # the spec pointer
    "https://agentskills.io/specification",
    # progressive disclosure, all three levels
    "progressive disclosure",
    "L1",
    "L2",
    "L3",
    "read_file",
    # catalog injection rule
    "auto-injected",
    "load_skill(list=true)",
    'load_skill(skill_name="',
    # fork-skill mechanics
    "context: fork",
    "isolated subagents",
    "own context window",
    "task prompt",
    "`response`",
    "work product",
    "session_id",
    "turn_count",
    # power skills -- every slash command and every behaviour
    "disable-model-invocation: true",
    "/code-review [focus]",
    "/mass-change <instruction>",
    "/session-debug [issue]",
    "code reuse, quality, efficiency",
    "5\u201330 independent units",
    "session-analyst",
    # bundle-author pointers
    "skills_dirs",
    "visibility",
    "config.skills",
    "#subdirectory=",
    "skills-assist",
    "authoring-guide.md",
    # skill-vs-agent decision
    "delegate",
    "parallel delegation",
]

# Long-form prose the lean rewrite removed. Its return means the head grew back.
CONTEXT_FORBIDDEN = [
    "You have access to the skills system for loading domain knowledge packages.",
    "## What Are Skills?",
    "## Skills Visibility",
    "## Available Tool: load_skill",
    "## Enhanced Skills (Fork Execution)",
    "### Built-in Power Skills",
    "## Skills Expert",
    "## Skills vs Agents",
    "| Skill | Slash Command | What It Does |",
    "Three power skills ship with the curated collection",
]


def test_context_file_stays_lean():
    chars = len(read_context())
    assert chars <= CONTEXT_CHARS_CEILING, (
        f"context/skills-instructions.md grew to {chars} chars (ceiling "
        f"{CONTEXT_CHARS_CEILING}, pinned at {CONTEXT_CHARS_AT_PIN}, stock was "
        f"{CONTEXT_CHARS_STOCK}). This file is in the always-on head -- paid for on every "
        "request of every session. If the growth is intentional, re-measure and move the pin."
    )


def test_context_file_keeps_every_rule():
    text = read_context()
    missing = [atom for atom in CONTEXT_REQUIRED if atom not in text]
    assert not missing, (
        "Rules/commands/pointers dropped from context/skills-instructions.md: "
        f"{missing}. Fidelity is the constraint the compression was allowed under."
    )


def test_context_file_stock_prose_not_restored():
    text = read_context()
    restored = [phrase for phrase in CONTEXT_FORBIDDEN if phrase in text]
    assert not restored, (
        f"Stock long-form prose restored in context/skills-instructions.md: {restored}. "
        "The lean rewrite carries the same rules in fewer characters."
    )


# --------------------------------------------------------------------------------------
# load_skill tool description
# --------------------------------------------------------------------------------------

LOAD_SKILL_REQUIRED = [
    "load_skill(list=True)",
    'load_skill(search="pattern")',
    'load_skill(info="skill-name")',
    'load_skill(skill_name="skill-name")',
    "name, description, version, license, path",
    "skill_directory",
    'read_file(skill_directory + "/examples/code.py")',
    "first-match-wins",
    ".amplifier/skills/",
    "~/.amplifier/skills/",
    "workspace",
]

LOAD_SKILL_FORBIDDEN = [
    "**List all skills:**",
    "**Search for skills:**",
    "**Get skill metadata:**",
    "**Load full skill content:**",
    "Usage Guidelines:",
    "Skill Discovery:",
]


def test_load_skill_description_stays_lean():
    chars = len(read_load_skill_description())
    assert chars <= LOAD_SKILL_CHARS_CEILING, (
        f"load_skill description grew to {chars} chars (ceiling {LOAD_SKILL_CHARS_CEILING}, "
        f"pinned at {LOAD_SKILL_CHARS_AT_PIN}, stock was {LOAD_SKILL_CHARS_STOCK}). Tool "
        "descriptions ship in the schema on every request. Re-measure before moving the pin."
    )


def test_load_skill_description_keeps_every_rule():
    text = read_load_skill_description()
    missing = [atom for atom in LOAD_SKILL_REQUIRED if atom not in text]
    assert not missing, f"Rules/commands dropped from the load_skill description: {missing}"


def test_load_skill_description_stock_prose_not_restored():
    text = read_load_skill_description()
    restored = [phrase for phrase in LOAD_SKILL_FORBIDDEN if phrase in text]
    assert not restored, (
        f"Stock long-form prose restored in the load_skill description: {restored}"
    )


def test_load_skill_description_has_no_leading_or_trailing_blank_line():
    """The stock block opened with a bare newline -- pure head cost, nothing else."""
    text = read_load_skill_description()
    assert text == text.strip(), (
        "load_skill description regained leading/trailing whitespace; the stock form opened "
        "with a blank line that cost characters on every request."
    )
