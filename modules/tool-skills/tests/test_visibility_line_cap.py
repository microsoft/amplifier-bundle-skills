"""Tests for the per-line character cap on the skills-visibility catalog.

The ``<system-reminder source="hooks-skills-visibility">`` block is composed by
``SkillsVisibilityHook._format_skills_list`` and injected into EVERY session's
head. It is a routing LIST, not a teaching surface: one line per skill, enough
to decide whether to load it, and the skill body carries the rest.

``visibility_line_char_cap`` enforces that shape with three guarantees, each
pinned below:

1. one physical line per skill (whitespace collapsed),
2. zero loss for descriptions already within the cap (verbatim),
3. the routing trigger survives condensing.

The final test pins the whole composed block byte-for-byte against a fixed
catalog, so the shape cannot silently drift back.
"""

from pathlib import Path

import pytest

from amplifier_module_tool_skills.discovery import SkillMetadata
from amplifier_module_tool_skills.hooks import DEFAULT_LINE_CHAR_CAP
from amplifier_module_tool_skills.hooks import SkillsVisibilityHook


def _skill(name: str, description: str, **kwargs) -> SkillMetadata:
    return SkillMetadata(
        name=name,
        description=description,
        path=Path(f"/skills/{name}/SKILL.md"),
        source="/skills",
        **kwargs,
    )


# --------------------------------------------------------------------------
# _condense: the three guarantees
# --------------------------------------------------------------------------


def test_description_within_the_cap_is_verbatim():
    """Guarantee 2: a lean description is byte-identical to its raw form."""
    text = "Renders a widget. Use when a widget is needed."
    assert SkillsVisibilityHook._condense(text, 180) == text


def test_whitespace_is_always_collapsed_to_one_line():
    """Guarantee 1: embedded newlines never reach the catalog."""
    raw = "Parses a config.\n\nOrder:\n  - defaults\n  - flags\n"
    out = SkillsVisibilityHook._condense(raw, 180)
    assert "\n" not in out
    assert out == "Parses a config. Order: - defaults - flags"


def test_trailing_trigger_survives_condensing():
    """Guarantee 3: the trigger sentence is reserved before the opening one.

    Descriptions in the wild put "Use when ..." LAST, so head-truncation drops
    exactly the sentence the catalog exists to carry.
    """
    text = (
        "Coordinates a long-running batch across several workers, tracking "
        "progress and retrying the legs that fail. Keeps a ledger of every "
        "attempt so a partial run can be resumed rather than restarted. "
        "Use when a batch must survive a crash midway."
    )
    out = SkillsVisibilityHook._condense(text, 160)
    assert len(out) <= 160
    assert "Use when a batch must survive a crash midway." in out


def test_trigger_wins_even_when_the_opening_sentence_is_huge():
    """A long opening sentence is clipped to make room for the trigger."""
    text = ("An opening sentence that runs on and on " * 6).strip() + ". Use when the caller asks."
    out = SkillsVisibilityHook._condense(text, 120)
    assert len(out) <= 120
    assert "Use when the caller asks." in out


def test_cap_is_never_exceeded_without_a_sentence_boundary():
    """A single unbroken sentence is word-boundary clipped and marked."""
    text = "word " * 80
    out = SkillsVisibilityHook._condense(text, 100)
    assert len(out) <= 100
    assert out.endswith("\u2026")


def test_zero_cap_disables_condensing_but_still_collapses_whitespace():
    raw = "First.\nSecond.\n"
    assert SkillsVisibilityHook._condense(raw, 0) == "First. Second."


def test_missing_config_key_uses_the_module_default():
    assert SkillsVisibilityHook({}, {}).line_char_cap == DEFAULT_LINE_CHAR_CAP


def test_invalid_cap_falls_back_to_the_module_default():
    hook = SkillsVisibilityHook({}, {"visibility_line_char_cap": "wat"})
    assert hook.line_char_cap == DEFAULT_LINE_CHAR_CAP


# --------------------------------------------------------------------------
# The cap reaches BOTH sections and the legacy mode
# --------------------------------------------------------------------------

_VERBOSE = (
    "Does a great many things across a great many surfaces, each of which "
    "takes a whole sentence to describe properly and none of which fit on "
    "one line. A second sentence of supporting detail. A third for luck. "
    "Use when the caller needs all of that at once."
)


@pytest.mark.asyncio
async def test_user_invoked_section_is_capped():
    """The token budget never covered this section -- the cap is its only bound."""
    skills = {"cmd": _skill("cmd", _VERBOSE, disable_model_invocation=True)}
    hook = SkillsVisibilityHook(skills, {"visibility_line_char_cap": 120})
    result = await hook.on_provider_request("provider:request", {})
    content = result.context_injection
    assert content is not None
    line = next(line for line in content.split("\n") if line.startswith("- **cmd**"))
    assert len(line) - len("- **cmd**: ") <= 120
    assert "Use when the caller needs all of that at once." in line


@pytest.mark.asyncio
async def test_legacy_count_mode_is_capped_too():
    """max_skills_visible mode renders through the same condenser."""
    skills = {"one": _skill("one", _VERBOSE)}
    hook = SkillsVisibilityHook(skills, {"max_skills_visible": 5, "visibility_line_char_cap": 120})
    result = await hook.on_provider_request("provider:request", {})
    content = result.context_injection
    assert content is not None
    line = next(line for line in content.split("\n") if line.startswith("- **one**"))
    assert len(line) - len("- **one**: ") <= 120


# --------------------------------------------------------------------------
# The drift pin
# --------------------------------------------------------------------------

# A fixed catalog exercising every path: a lean description (verbatim), a
# trailing trigger (reserved), embedded newlines (collapsed), a single
# unbroken over-long sentence (clipped), and both sections.
PINNED_CATALOG = {
    "alpha-short": _skill("alpha-short", "Renders a widget."),
    "bravo-trailing-trigger": _skill(
        "bravo-trailing-trigger",
        "Coordinates a long-running batch across several workers, tracking "
        "progress and retrying the legs that fail. Keeps a ledger of every "
        "attempt so a partial run can be resumed rather than restarted. "
        "Use when a batch must survive a crash midway.",
    ),
    "charlie-multiline": _skill(
        "charlie-multiline",
        "Parses a config file.\n\nHandles the merge order:\n  - defaults\n  - file\n  - flags\n",
    ),
    "delta-one-sentence": _skill(
        "delta-one-sentence",
        "A single unbroken sentence that simply keeps going and going without "
        "any terminator at all so there is no sentence boundary anywhere at "
        "all for the condenser to cut on cleanly no matter how hard it looks",
    ),
    "zulu-command": _skill(
        "zulu-command", "Opens the review panel.", disable_model_invocation=True
    ),
    "yankee-command": _skill(
        "yankee-command",
        "Runs the full audit sweep over the workspace and writes a report to "
        "disk, then opens it. Use when a release is about to be cut.",
        disable_model_invocation=True,
    ),
}

PINNED_BLOCK = (
    '<system-reminder source="hooks-skills-visibility">\n'
    "Available skills (use load_skill tool):\n"
    "\n"
    "- **alpha-short**: Renders a widget.\n"
    "- **bravo-trailing-trigger**: Coordinates a long-running batch across several "
    "workers, tracking progress and retrying the legs that fail. \u2026 Use when a batch "
    "must survive a crash midway.\n"
    "- **charlie-multiline**: Parses a config file. Handles the merge order: - defaults "
    "- file - flags\n"
    "- **delta-one-sentence**: A single unbroken sentence that simply keeps going and "
    "going without any terminator at all so there is no sentence boundary anywhere at "
    "all for the condenser to cut on cleanly\u2026\n"
    "\n"
    "User-invoked skills (available via /command):\n"
    "\n"
    "- **yankee-command**: Runs the full audit sweep over the workspace and writes a "
    "report to disk, then opens it. Use when a release is about to be cut.\n"
    "- **zulu-command**: Opens the review panel.\n"
    "</system-reminder>"
)


def test_composed_block_is_pinned_to_the_lean_shape():
    """Byte-exact pin of the composed block for a fixed catalog.

    This is the drift guard: any change to the wrapper, the two headers, the
    line shape, or the condenser shows up here as a diff rather than as a
    silently fatter always-on head.
    """
    hook = SkillsVisibilityHook(
        PINNED_CATALOG,
        {"visibility_token_budget": 5000, "visibility_line_char_cap": 180},
    )
    assert hook._format_skills_list(PINNED_CATALOG) == PINNED_BLOCK


def test_block_is_exactly_one_physical_line_per_skill():
    """AC2's "yields the v1 shape" made checkable: ONE LINE PER SKILL, exactly.

    The v1 captured head is 57 physical lines for 50 skills — 7 template lines
    (wrapper open/close, two headers, three blanks) plus one line per skill and
    not one more. Stock spilled multi-paragraph descriptions across extra
    physical lines; this asserts the composed block never does.
    """
    hook = SkillsVisibilityHook(
        PINNED_CATALOG,
        {"visibility_token_budget": 5000, "visibility_line_char_cap": 180},
    )
    block = hook._format_skills_list(PINNED_CATALOG)
    physical = block.split("\n")
    # 7 template lines when both sections are present.
    assert len(physical) == len(PINNED_CATALOG) + 7, physical
    # `charlie-multiline` carries embedded newlines; it must still be one line.
    charlie = [line for line in physical if "charlie-multiline" in line]
    assert len(charlie) == 1


def test_pinned_block_holds_the_shape_invariants():
    """The pin above is not just a string -- it encodes the contract."""
    lines = PINNED_BLOCK.split("\n")
    skill_lines = [line for line in lines if line.startswith("- **")]
    # One physical line per skill: every skill in, every line accounted for.
    assert len(skill_lines) == len(PINNED_CATALOG)
    # Both command pointers survive.
    assert "load_skill" in PINNED_BLOCK
    assert "/command" in PINNED_BLOCK
    # No line spends more than the cap on description text.
    for line in skill_lines:
        name, _, description = line.partition("**: ")
        assert len(description) <= 180, line
