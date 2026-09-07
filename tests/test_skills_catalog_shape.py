"""Pin the shape of the curated skills catalog (model_performance-4br4).

Three decisions are pinned here, each of which is invisible at runtime if it
silently reverts -- a skill that quietly rejoins the model-invocable index costs
always-on tokens on every request in every session, and nothing turns red.

1. PERSONA LENSES are user-invoked only, EXCEPT the two the owner kept visible.
   The council skills load their lenses BY NAME, so hiding a lens does not
   break a council -- `disable-model-invocation` only decides which section of
   the visibility block a skill is advertised in, never whether `load_skill`
   can resolve it.

2. HAND-RUN AUTHORING TOOLS are user-invoked only. Owner, 2026-09-07, verbatim:
   "all of those authoring ones are ones we run by hand, so they can be hidden".

3. The `*-patterns` skills are FOLDED into one `engineering-patterns` umbrella,
   with every original body surviving as an L3 reference file. Nothing was
   deleted; the count check below is what makes "folded, not dropped" a fact
   rather than a claim.
"""

import re
from pathlib import Path

SKILLS = Path(__file__).parent.parent / "skills"

# Lenses the owner ordered hidden.
HIDDEN_LENSES = [
    "bet-sizer",
    "cranky-old-sam",
    "crusty-old-engineer",
    "intent-keeper",
    "outcome-cartographer",
    "outcomist",
    "positioning-critic",
    "user-advocate",
]

# Lenses that keep full visibility: both earn it on standalone (non-council)
# use -- tester-breaker 385, restless-old-brian 236.
VISIBLE_LENSES = ["tester-breaker", "restless-old-brian"]

# Authoring tools a person runs by hand via /command.
HAND_RUN_AUTHOR_TOOLS = ["adapt-skill", "councilify", "personafy", "skillify"]

# The 13 pattern guides folded into the umbrella. The program directive said 12;
# 13 is what this repo actually carried (one-line-installer-patterns was the
# uncounted one), and the count is pinned here so the discrepancy cannot recur.
FOLDED_PATTERNS = [
    "amplifier-tool-leverage-patterns",
    "auth-tls-patterns",
    "cli-packaging-patterns",
    "config-state-patterns",
    "container-orchestration-patterns",
    "file-ipc-patterns",
    "http-service-patterns",
    "instance-storage-patterns",
    "msgraph-integration-patterns",
    "one-line-installer-patterns",
    "plugin-discovery-patterns",
    "react-microfrontend-patterns",
    "self-managing-tool-patterns",
]

UMBRELLA = "engineering-patterns"

_HIDDEN_RE = re.compile(r"^disable-model-invocation:\s*true\s*$", re.MULTILINE)


def frontmatter(name: str) -> str:
    path = SKILLS / name / "SKILL.md"
    assert path.exists(), f"Expected a skill at {path}"
    match = re.match(r"^---\n(.*?)\n---", path.read_text(encoding="utf-8"), re.DOTALL)
    assert match, f"{path} must have YAML frontmatter delimited by ---"
    return match.group(1)


# --- 1 + 2: who is hidden, who is not ---------------------------------------


def test_hidden_skills_are_hidden():
    """Every lens and authoring tool the owner named is user-invoked only."""
    missing = [
        name
        for name in HIDDEN_LENSES + HAND_RUN_AUTHOR_TOOLS
        if not _HIDDEN_RE.search(frontmatter(name))
    ]
    assert not missing, (
        f"These must carry 'disable-model-invocation: true' but do not: {missing}"
    )


def test_kept_lenses_stay_model_invocable():
    """The two exceptions keep FULL visibility -- they earn it standalone."""
    wrongly_hidden = [
        name for name in VISIBLE_LENSES if _HIDDEN_RE.search(frontmatter(name))
    ]
    assert not wrongly_hidden, (
        f"These lenses must stay model-invocable: {wrongly_hidden}. "
        "tester-breaker and restless-old-brian are used standalone far more "
        "often than they are convened by a council."
    )


def test_hidden_skills_stay_user_invocable():
    """Hiding a skill from the model must not hide it from the USER too.

    `disable-model-invocation` without `user-invocable: true` produces a skill
    nothing can reach: not the model, not a /command. That is a silent loss of
    the skill, and it is exactly the failure this catalog change must not cause.
    """
    unreachable = [
        name
        for name in HIDDEN_LENSES + HAND_RUN_AUTHOR_TOOLS
        if not re.search(r"^user-invocable:\s*true\s*$", frontmatter(name), re.MULTILINE)
    ]
    assert not unreachable, (
        f"Hidden from the model AND not user-invocable, so unreachable: {unreachable}"
    )


# --- 3: the patterns fold ----------------------------------------------------


def test_folded_patterns_are_no_longer_standalone_skills():
    """No folded pattern may still be its own catalog entry."""
    still_standalone = [n for n in FOLDED_PATTERNS if (SKILLS / n / "SKILL.md").exists()]
    assert not still_standalone, (
        f"These were folded into {UMBRELLA} but still exist as skills: "
        f"{still_standalone}"
    )


def test_every_folded_body_survives_as_a_reference():
    """Folded, NOT deleted: each original body is an L3 reference file."""
    refs = SKILLS / UMBRELLA / "references"
    missing = [n for n in FOLDED_PATTERNS if not (refs / f"{n}.md").exists()]
    assert not missing, f"Folded bodies missing from {refs}: {missing}"

    extra = sorted(p.stem for p in refs.glob("*.md") if p.stem not in FOLDED_PATTERNS)
    assert not extra, f"Unexpected reference files in {refs}: {extra}"


def test_umbrella_description_names_every_folded_topic():
    """The one catalog line must advertise all thirteen topics.

    Checked against a keyword per topic rather than the skill's own name: the
    description has to fit the shipped 180-char render cap
    (`visibility_line_char_cap`), so it names topics in shorthand. A test that
    demanded full skill names would force a description that gets truncated at
    render time -- which loses the trailing topics for real.
    """
    fm = frontmatter(UMBRELLA).lower()
    keywords = [
        "cli packaging",
        "installers",
        "config/state",
        "http",
        "auth/tls",
        "file ipc",
        "plugins",
        "instance storage",
        "containers",
        "react mfe",
        "graph",
        "self-update",
        "tool leverage",
    ]
    assert len(keywords) == len(FOLDED_PATTERNS)
    missing = [k for k in keywords if k not in fm]
    assert not missing, f"{UMBRELLA} description does not name: {missing}"


def test_umbrella_description_fits_the_render_cap():
    """Fit the shipped cap so the catalog line renders VERBATIM.

    `SkillsVisibilityHook._condense` returns a description unchanged when it is
    within `visibility_line_char_cap` (default 180) and otherwise clips it with
    an ellipsis. Over the cap, the trailing topics -- the ones a router needs
    most, since they are the least guessable -- are the first to go.
    """
    cap = 180
    match = re.search(
        r'^description:\s*"(.*)"\s*$', frontmatter(UMBRELLA), re.MULTILINE | re.DOTALL
    )
    assert match, f"{UMBRELLA} must carry a single-line quoted description"
    description = " ".join(match.group(1).split())
    assert len(description) <= cap, (
        f"{UMBRELLA} description is {len(description)} chars, over the {cap}-char "
        "render cap — it would be truncated in the always-on catalog"
    )


def test_umbrella_body_points_at_every_reference():
    """Every reference must be reachable from the umbrella's own index."""
    body = (SKILLS / UMBRELLA / "SKILL.md").read_text(encoding="utf-8")
    missing = [n for n in FOLDED_PATTERNS if f"references/{n}.md" not in body]
    assert not missing, f"{UMBRELLA} body does not link: {missing}"
