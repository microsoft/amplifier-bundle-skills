"""Tests for the token-budget tier rendering of the skills-visibility index.

The visibility hook must render EVERY effective, visible skill at least by name.
Its DMI-independent plan assigns the model-invocable entries a detail tier while
spending at most ``visibility_token_budget`` tokens for the complete wrapped
block. Coverage is the invariant — no skill is ever dropped — and the budget
bounds detail (name-only index, one-line summary, or full description).
"""

import re
from pathlib import Path

import pytest

from amplifier_module_tool_skills.discovery import SkillMetadata
from amplifier_module_tool_skills.discovery import discover_skills
from amplifier_module_tool_skills.hooks import DEFAULT_VISIBILITY_TOKEN_BUDGET
from amplifier_module_tool_skills.hooks import SkillsVisibilityHook
from amplifier_module_tool_skills import SkillsDiscovery


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


def _regular_names(content: str) -> list[str]:
    """Ordered skill names from both sections, in rendered section order."""
    names = []
    for line in content.split("\n"):
        if line.startswith("- **"):
            names.append(line.split("**")[1])
    return names


def _skill_line_by_name(content: str) -> dict[str, str]:
    """Return each rendered skill line keyed by its exact skill name."""
    return {
        line.split("**")[1]: line
        for line in content.splitlines()
        if line.startswith("- **")
    }


# --------------------------------------------------------------------------
# Mode selection / back-compat (design item 4)
# --------------------------------------------------------------------------


def test_default_config_is_budget_mode():
    """No config -> budget mode with the module default."""
    hook = SkillsVisibilityHook({}, {})
    assert hook._budget_mode is True
    assert hook.token_budget == DEFAULT_VISIBILITY_TOKEN_BUDGET


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
    assert hook.token_budget == DEFAULT_VISIBILITY_TOKEN_BUDGET


# --------------------------------------------------------------------------
# Full coverage and complete-block budget (design item 2a — the invariant)
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
    """The complete wrapped estimate stays within budget and detail is capped
    (some skills remain name-only) while coverage is complete."""
    budget = 400
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
    # Budget respected: the whole wrapped block is measured, not one section.
    assert len(content) // 4 <= budget
    # Cap engaged: not every skill could be upgraded — at least one is index-only.
    index_only = [
        line
        for line in content.split("\n")
        if line.startswith("- **") and line.endswith("**")
    ]
    assert index_only, "expected at least one name-only skill under a tight budget"


# --------------------------------------------------------------------------
# Whole-block DMI transition matrix
# --------------------------------------------------------------------------


def _transition_catalog(kind: str) -> tuple[dict[str, SkillMetadata], tuple[str, ...]]:
    """Build a catalog and its regular skills to switch to manual together."""
    if kind == "empty":
        return {}, ()
    if kind == "typical":
        return (
            {
                "alpha": _skill("alpha", "Alpha routing detail. Use when alpha is needed."),
                "bravo": _skill("bravo", "Bravo routing detail. Use when bravo is needed."),
                "charlie": _skill(
                    "charlie", "Charlie routing detail. Use when charlie is needed."
                ),
                "delta": _skill("delta", "Delta routing detail. Use when delta is needed."),
            },
            ("bravo", "charlie"),
        )
    if kind == "saturated":
        description = (
            "Long routing detail that competes for scarce catalog room. "
            "Use when this saturated skill is needed. "
            + "tail " * 80
        )
        return (
            {
                f"skill-{index:02d}": _skill(f"skill-{index:02d}", description)
                for index in range(40)
            },
            ("skill-10", "skill-20"),
        )
    if kind == "all-manual":
        return (
            {
                "command-a": _skill(
                    "command-a", "Manual command A.", disable_model_invocation=True
                ),
                "command-b": _skill(
                    "command-b", "Manual command B.", disable_model_invocation=True
                ),
            },
            (),
        )
    if kind == "mixed-unicode":
        return (
            {
                "café": _skill("café", "Prépare des données. Use when data needs care."),
                "東京": _skill("東京", "東京の作業を行う。Use when Japanese data is needed."),
                "manual-λ": _skill(
                    "manual-λ",
                    "Already manual routing detail.",
                    disable_model_invocation=True,
                ),
            },
            ("café", "東京"),
        )
    raise AssertionError(f"Unknown catalog kind: {kind}")


@pytest.mark.parametrize(
    "kind,budget",
    [
        ("typical", 500),
        ("saturated", 220),
        ("empty", 220),
        ("all-manual", 220),
        ("mixed-unicode", 500),
    ],
)
def test_budget_catalog_transition_matrix_preserves_names_and_never_grows(
    kind: str, budget: int
):
    """Whole blocks cover normal, tight, empty, manual, mixed, and Unicode cases."""
    before_skills, targets = _transition_catalog(kind)
    hook = SkillsVisibilityHook(
        before_skills, {"visibility_token_budget": budget, "visibility_line_char_cap": 180}
    )
    before = hook._format_skills_list(before_skills)

    if not before_skills:
        assert before == ""
        return

    # The invariant skeleton is present even for all-manual catalogs.
    assert "Available skills (use load_skill tool):" in before
    assert "Manual skills (load by name; /name when user-invocable):" in before
    assert _regular_names(before) == list(_skill_line_by_name(before))
    assert set(_skill_line_by_name(before)) == set(before_skills)
    assert len(_skill_line_by_name(before)) == len(before_skills)

    if not targets:
        return

    assert len(targets) >= 2
    for target in targets:
        before_skills[target].disable_model_invocation = True
    after = hook._format_skills_list(before_skills)

    # Measure the complete rendered string in both Python characters and bytes.
    assert len(after) <= len(before)
    assert len(after.encode("utf-8")) <= len(before.encode("utf-8"))
    assert set(_skill_line_by_name(after)) == set(before_skills)
    assert len(_skill_line_by_name(after)) == len(before_skills)
    for target in targets:
        assert _skill_line_by_name(after)[target] == f"- **{target}**"


def test_dmi_transition_does_not_reallocate_regular_routing_detail():
    """A manual transition cannot upgrade an unchanged model-invocable line."""
    description = (
        "A concise opening sentence. Use when this routing detail is relevant. "
        + "extra " * 50
    )
    skills = {
        "alpha": _skill("alpha", description),
        "bravo": _skill("bravo", description),
        "charlie": _skill("charlie", description),
        "delta": _skill("delta", description),
    }
    hook = SkillsVisibilityHook(
        skills, {"visibility_token_budget": 150, "visibility_line_char_cap": 180}
    )
    before = hook._format_skills_list(skills)
    before_lines = _skill_line_by_name(before)

    skills["bravo"].disable_model_invocation = True
    skills["charlie"].disable_model_invocation = True
    after = hook._format_skills_list(skills)
    after_lines = _skill_line_by_name(after)

    assert after_lines["bravo"] == "- **bravo**"
    assert after_lines["charlie"] == "- **charlie**"
    for name in {"alpha", "delta"}:
        assert after_lines[name] == before_lines[name]


def test_overflow_reports_complete_name_floor_and_retains_every_name():
    """Floor overflow is explicit, DMI-independent, and never drops coverage."""
    skills = {
        "alpha": _skill("alpha", "Alpha detail."),
        "bravo": _skill("bravo", "Bravo detail."),
        "manual": _skill("manual", "Manual detail.", disable_model_invocation=True),
    }
    hook = SkillsVisibilityHook(skills, {"visibility_token_budget": 1})
    before = hook._format_skills_list(skills)

    skills["alpha"].disable_model_invocation = True
    skills["bravo"].disable_model_invocation = True
    after = hook._format_skills_list(skills)

    for content in (before, after):
        assert "Name-only catalog floor:" in content
        assert "configured budget: 1" in content
        assert "load_skill(list=true)" in content
        assert 'load_skill(search="…")' in content
        assert set(_skill_line_by_name(content)) == set(skills)
        assert len(_skill_line_by_name(content)) == len(skills)
    assert len(after) <= len(before)
    assert len(after.encode("utf-8")) <= len(before.encode("utf-8"))
    # DMI changes placement but not the complete planned name floor.
    floor_pattern = r"Name-only catalog floor: (\d+) tokens exceeds"
    assert re.search(floor_pattern, before).group(1) == re.search(
        floor_pattern, after
    ).group(1)


def test_manual_skill_heading_distinguishes_exact_loads_from_shortcuts():
    """DMI-only skills retain an exact-name affordance without a false shortcut."""
    manual_only = _skill(
        "manual-only",
        "Can be loaded by exact name.",
        disable_model_invocation=True,
    )
    goalify = _skill(
        "goalify",
        "Writes a measurable goal condition.",
        disable_model_invocation=True,
        user_invocable=True,
        shortcut="goal",
    )
    skills = {"manual-only": manual_only, "goalify": goalify}
    content = SkillsVisibilityHook(
        skills, {"visibility_token_budget": 200}
    )._format_skills_list(skills)

    assert (
        "Manual skills (load by name; /name when user-invocable):\n\n"
        "- **goalify**\n- **manual-only**"
    ) in content
    shortcuts = SkillsDiscovery(skills).get_shortcuts()
    assert "manual-only" not in shortcuts
    assert shortcuts["goalify"]["name"] == "goalify"
    assert shortcuts["goal"]["name"] == "goalify"


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
async def test_summary_fallback_condenses_and_keeps_the_trigger():
    """The summary tier condenses to HALF the line cap and keeps the routing
    trigger, which the old first-sentence fallback dropped.

    A description's first sentence says what a skill IS; its trigger ("Use
    when ...") is usually last, so summarising to the first sentence stripped
    the one part a routing catalog exists to carry.
    """
    skills = {
        "summary-skill": _skill(
            "summary-skill",
            "Does a thing with several moving parts that take a while to say. "
            "A middle sentence carrying detail nobody ever routes on at all. "
            "Use when the caller needs that thing done.",
        )
    }
    # Budget tuned so this single skill reaches the summary tier but not full,
    # after the complete wrapper and the invariant second section are reserved.
    hook = SkillsVisibilityHook(
        skills, {"visibility_token_budget": 75, "visibility_line_char_cap": 200}
    )
    result = await hook.on_provider_request("provider:request", {})
    content = result.context_injection
    assert content is not None
    line = next(
        line for line in content.split("\n") if line.startswith("- **summary-skill**")
    )
    # Summary tier engaged: shorter than the full description ...
    full = "- **summary-skill**: " + skills["summary-skill"].description
    assert len(line) < len(full)
    # ... the opening survives ...
    assert "Does a thing" in line
    # ... and so does the trigger.
    assert "Use when the caller needs that thing done." in line


@pytest.mark.asyncio
async def test_explicit_summary_override_used_at_summary_tier():
    """An explicit visibility.summary is preferred over the derived one-liner."""
    skill = _skill(
        "override-skill",
        "A long description sentence that would otherwise be the fallback summary text.",
    )
    skill.visibility = {"summary": "Curated one-liner."}
    hook = SkillsVisibilityHook({"override-skill": skill}, {"visibility_token_budget": 60})
    result = await hook.on_provider_request("provider:request", {})
    content = result.context_injection
    assert content is not None
    assert "- **override-skill**: Curated one-liner." in content


# --------------------------------------------------------------------------
# Legacy count mode (design item 4 — unchanged behavior)
# --------------------------------------------------------------------------


def test_only_max_skills_visible_keeps_the_legacy_block_byte_for_byte():
    """Count-cap-only config retains conditional sections and manual detail."""
    skills = {
        "alpha": _skill("alpha", "Alpha detail."),
        "manual": _skill(
            "manual", "Manual detail.", disable_model_invocation=True
        ),
    }

    block = SkillsVisibilityHook(
        skills, {"max_skills_visible": 50}
    )._format_skills_list(skills)

    assert block == (
        '<system-reminder source="hooks-skills-visibility">\n'
        "Available skills (use load_skill tool):\n"
        "\n"
        "- **alpha**: Alpha detail.\n"
        "\n"
        "User-invoked skills (available via /command):\n"
        "\n"
        "- **manual**: Manual detail.\n"
        "</system-reminder>"
    )


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
