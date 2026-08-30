"""Tests for the token-budget tier rendering of the skills-visibility index.

The visibility hook must render EVERY regular (model-invocable) skill at some
detail tier while spending at most ``visibility_token_budget`` tokens of
detail. Coverage is the invariant — no skill is ever dropped — and the budget
bounds only how much detail each skill gets (name-only index, one-line summary,
or full description).
"""

from pathlib import Path

import pytest

from amplifier_module_tool_skills.discovery import SkillMetadata
from amplifier_module_tool_skills.discovery import discover_skills
from amplifier_module_tool_skills.hooks import SkillsVisibilityHook


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _skill(name: str, description: str, **kwargs) -> SkillMetadata:
    return SkillMetadata(
        name=name,
        description=description,
        path=Path(f"/skills/{name}/SKILL.md"),
        source="/skills",
        **kwargs,
    )


def _regular_section(content: str) -> str:
    """Extract the regular-skills section text (header + skill lines) from an
    injected system-reminder block with no user-invoked section."""
    inner = content.split(">\n", 1)[1].rsplit("\n</system-reminder>", 1)[0]
    return inner


def _regular_names(content: str) -> list[str]:
    """Ordered skill names from the regular section, in render order."""
    names = []
    for line in content.split("\n"):
        if line.startswith("- **"):
            names.append(line.split("**")[1])
    return names


# --------------------------------------------------------------------------
# Mode selection / back-compat (design item 4)
# --------------------------------------------------------------------------


def test_default_config_is_budget_mode():
    """No config -> budget mode with the 5000-token default."""
    hook = SkillsVisibilityHook({}, {})
    assert hook._budget_mode is True
    assert hook.token_budget == 5000


def test_only_max_skills_visible_is_legacy_mode():
    """max_skills_visible present, no budget -> legacy count-cap mode."""
    hook = SkillsVisibilityHook({}, {"max_skills_visible": 10})
    assert hook._budget_mode is False


def test_budget_wins_when_both_present():
    """Both keys set -> budget mode wins (design item 4)."""
    hook = SkillsVisibilityHook({}, {"visibility_token_budget": 5000, "max_skills_visible": 3})
    assert hook._budget_mode is True
    assert hook.token_budget == 5000


def test_invalid_budget_falls_back_to_default():
    """A non-numeric budget degrades to the default rather than crashing."""
    hook = SkillsVisibilityHook({}, {"visibility_token_budget": "not-a-number"})
    assert hook._budget_mode is True
    assert hook.token_budget == 5000


# --------------------------------------------------------------------------
# Full coverage (design item 2a — the invariant)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_skills_present_at_default_budget():
    """Every skill is advertised at the default budget; small skills all get
    their full description (nothing is dropped, unlike the old alpha cap)."""
    skills = {
        f"skill-{i:03d}": _skill(f"skill-{i:03d}", f"Description for skill number {i}.")
        for i in range(60)
    }
    hook = SkillsVisibilityHook(skills, {})  # default budget mode, 5000
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    content = result.context_injection
    assert content is not None
    # Every one of the 60 skills is present (the old cap stopped at 50).
    for i in range(60):
        assert f"skill-{i:03d}" in content
    assert len(_regular_names(content)) == 60
    # Small skills at a generous budget render their full description.
    assert "Description for skill number 59." in content
    # No legacy truncation footer.
    assert "more - use load_skill(list=true)" not in content


@pytest.mark.asyncio
async def test_full_coverage_even_when_floor_exceeds_budget():
    """A pathologically small budget still lists every skill (name-only)."""
    skills = {
        f"skill-{i:03d}": _skill(f"skill-{i:03d}", f"Description {i}.")
        for i in range(40)
    }
    hook = SkillsVisibilityHook(skills, {"visibility_token_budget": 1})
    result = await hook.on_provider_request("provider:request", {})

    content = result.context_injection
    assert content is not None
    names = _regular_names(content)
    assert len(names) == 40  # coverage wins over budget
    # With budget 1, no skill can be upgraded past the name-only index tier.
    for line in content.split("\n"):
        if line.startswith("- **"):
            assert line.endswith("**"), f"unexpected detail on: {line!r}"


# --------------------------------------------------------------------------
# Budget respected (design item 1 + 2)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_respected():
    """The regular-section token estimate stays within budget and detail is
    capped (some skills remain name-only) while coverage is complete."""
    budget = 800
    long_desc = "This is a fairly long single sentence description without any early terminator so its first sentence spans well past the summary truncation window " + ("x" * 120)
    skills = {
        f"skill-{i:03d}": _skill(f"skill-{i:03d}", long_desc)
        for i in range(30)
    }
    hook = SkillsVisibilityHook(skills, {"visibility_token_budget": budget})
    result = await hook.on_provider_request("provider:request", {})

    content = result.context_injection
    assert content is not None
    # Coverage: all 30 skills present.
    assert len(_regular_names(content)) == 30
    # Budget respected: regular-section token estimate within budget (the floor
    # of name-only lines fits inside this budget, so the whole section must).
    section = _regular_section(content)
    assert len(section) // 4 <= budget
    # Cap engaged: not every skill could be upgraded — at least one is index-only.
    index_only = [
        line
        for line in content.split("\n")
        if line.startswith("- **") and line.endswith("**")
    ]
    assert index_only, "expected at least one name-only skill under a tight budget"


@pytest.mark.asyncio
async def test_budget_upgrades_in_tiers():
    """A middling budget upgrades some skills to summary/full while leaving
    others at index — proving graduated detail rather than all-or-nothing."""
    # Descriptions with a short first sentence (cheap summary) + long tail
    # (expensive full description).
    desc = "Short summary sentence. " + ("tail " * 60)
    skills = {f"s{i:02d}": _skill(f"s{i:02d}", desc) for i in range(20)}
    # Budget chosen to sit between the all-index floor and the all-summary cost,
    # so some skills reach summary while others stay name-only.
    hook = SkillsVisibilityHook(skills, {"visibility_token_budget": 120})
    result = await hook.on_provider_request("provider:request", {})

    content = result.context_injection
    assert content is not None
    lines = [line for line in content.split("\n") if line.startswith("- **")]
    tiers = {
        "index": [line for line in lines if line.endswith("**")],
        "detailed": [line for line in lines if "**: " in line],
    }
    assert len(lines) == 20  # full coverage
    assert tiers["detailed"], "expected at least one upgraded (detailed) skill"
    assert tiers["index"], "expected at least one name-only skill"


# --------------------------------------------------------------------------
# Priority reordering (design item 3)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_priority_reorders_render_order():
    """Higher visibility.priority sorts earlier regardless of name."""
    a = _skill("aaa", "Alpha skill.")
    b = _skill("bbb", "Bravo skill.")
    c = _skill("ccc", "Charlie skill.")
    # c is alphabetically last but highest priority -> renders first.
    c.visibility = {"priority": 10}
    b.visibility = {"priority": 5}
    skills = {"aaa": a, "bbb": b, "ccc": c}

    hook = SkillsVisibilityHook(skills, {})  # generous default budget
    result = await hook.on_provider_request("provider:request", {})
    content = result.context_injection
    assert content is not None
    assert _regular_names(content) == ["ccc", "bbb", "aaa"]


@pytest.mark.asyncio
async def test_equal_priority_breaks_ties_alphabetically():
    """Ties (all default priority 0) preserve alphabetical order."""
    skills = {
        "gamma": _skill("gamma", "G."),
        "alpha": _skill("alpha", "A."),
        "beta": _skill("beta", "B."),
    }
    hook = SkillsVisibilityHook(skills, {})
    result = await hook.on_provider_request("provider:request", {})
    content = result.context_injection
    assert content is not None
    assert _regular_names(content) == ["alpha", "beta", "gamma"]


# --------------------------------------------------------------------------
# Summary tier (design item 3 — fallback + explicit override)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_fallback_is_first_sentence():
    """When a skill lands at the summary tier and has no explicit summary, the
    one-liner is the description's first sentence."""
    skills = {
        "summary-skill": _skill(
            "summary-skill",
            "First sentence here. Second sentence must not appear in the summary at all.",
        )
    }
    # Budget tuned so this single skill reaches the summary tier but not full.
    hook = SkillsVisibilityHook(skills, {"visibility_token_budget": 25})
    result = await hook.on_provider_request("provider:request", {})
    content = result.context_injection
    assert content is not None
    assert "- **summary-skill**: First sentence here." in content
    assert "Second sentence" not in content


def test_first_sentence_truncated_to_140_chars():
    """The first-sentence fallback is truncated to 140 characters."""
    long_sentence = "word " * 60  # 300 chars, no sentence terminator
    summary = SkillsVisibilityHook._first_sentence(long_sentence)
    assert len(summary) <= 140
    assert summary.endswith("...")


def test_first_sentence_stops_at_terminator():
    """The fallback stops at the first sentence terminator."""
    assert SkillsVisibilityHook._first_sentence("Hello world. Ignore this.") == "Hello world."


@pytest.mark.asyncio
async def test_explicit_summary_override_used_at_summary_tier():
    """An explicit visibility.summary is preferred over the derived one-liner."""
    skill = _skill(
        "override-skill",
        "A long description sentence that would otherwise be the fallback summary text.",
    )
    skill.visibility = {"summary": "Curated one-liner."}
    hook = SkillsVisibilityHook({"override-skill": skill}, {"visibility_token_budget": 20})
    result = await hook.on_provider_request("provider:request", {})
    content = result.context_injection
    assert content is not None
    assert "- **override-skill**: Curated one-liner." in content


# --------------------------------------------------------------------------
# Legacy count mode (design item 4 — unchanged behavior)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_count_mode_truncates_with_footer():
    """max_skills_visible without a budget keeps the legacy alpha cap + footer."""
    skills = {
        f"skill-{i:03d}": _skill(f"skill-{i:03d}", f"Skill {i}")
        for i in range(10)
    }
    hook = SkillsVisibilityHook(skills, {"max_skills_visible": 3})
    result = await hook.on_provider_request("provider:request", {})

    content = result.context_injection
    assert content is not None
    names = _regular_names(content)
    assert names == ["skill-000", "skill-001", "skill-002"]
    assert "(7 more - use load_skill(list=true) to see all)_" in content


@pytest.mark.asyncio
async def test_budget_mode_has_no_legacy_footer_when_both_keys_present():
    """With both keys present, budget mode wins: all skills shown, no footer."""
    skills = {
        f"skill-{i:03d}": _skill(f"skill-{i:03d}", f"Skill {i}")
        for i in range(10)
    }
    hook = SkillsVisibilityHook(
        skills, {"visibility_token_budget": 5000, "max_skills_visible": 3}
    )
    result = await hook.on_provider_request("provider:request", {})
    content = result.context_injection
    assert content is not None
    assert len(_regular_names(content)) == 10
    assert "more - use load_skill(list=true)" not in content


# --------------------------------------------------------------------------
# Frontmatter plumbing end-to-end (design item 7)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_visibility_frontmatter_read_from_disk(tmp_path):
    """A skill's `visibility:` mapping is honored when carried only in the
    SKILL.md frontmatter on disk (proves plumbing without a metadata field)."""
    for name, priority, summary in (
        ("aaa-low", 0, "Low priority one-liner."),
        ("zzz-high", 10, "High priority one-liner."),
    ):
        d = tmp_path / name
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\n"
            f"name: {name}\n"
            f"description: Full description for {name} skill.\n"
            "visibility:\n"
            f"  priority: {priority}\n"
            f"  summary: {summary}\n"
            "---\n"
            "# body\n"
        )

    skills = discover_skills(tmp_path)
    hook = SkillsVisibilityHook(skills, {})

    # Priority read from disk reorders: high-priority renders first.
    result = await hook.on_provider_request("provider:request", {})
    content = result.context_injection
    assert content is not None
    assert _regular_names(content) == ["zzz-high", "aaa-low"]

    # Explicit summary read from disk is used at the summary tier.
    meta = skills["zzz-high"]
    assert hook._skill_priority(meta) == 10
    assert hook._skill_summary(meta) == "High priority one-liner."
