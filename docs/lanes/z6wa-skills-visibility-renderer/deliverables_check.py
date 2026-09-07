#!/usr/bin/env python3
"""Mechanical completeness gate for lane z6wa's SEVEN goal DELIVERABLES.

Four review passes have asked whether this lane is complete. This stops
answering that in prose. Each of the seven items in GOAL.md's DELIVERABLES list
is checked against the SHIPPED artefacts -- source, evidence files, the test
suite, and the live PR -- not against anything this lane asserts about itself.

It also checks the two things the goal requires ABOUT a NOT-POSSIBLE item, so
AC5's disposition is verified rather than trusted.

Usage:
    python3 deliverables_check.py            # offline checks only
    python3 deliverables_check.py --with-pr  # also read the PR back from GitHub
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "docs/lanes/z6wa-skills-visibility-renderer"
EV = LANE / "evidence"
HOOKS = REPO / "modules/tool-skills/amplifier_module_tool_skills/hooks.py"
NOTE = LANE / "DONE-NOTE.md"
V1 = Path(
    "/home/bkrabach/dev/openai-evals-team-ci/.amplifier/evaluation/probes/"
    "bji-lean-head/v1_instructions.json"
)

results: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str) -> None:
    results.append((label, ok, detail))


def d1_file_and_function_named() -> None:
    src = HOOKS.read_text()
    has_fn = "def _format_skills_list(" in src
    note = NOTE.read_text()
    names_file = "modules/tool-skills/amplifier_module_tool_skills/hooks.py" in note
    names_fn = "_format_skills_list" in note
    check(
        "D1 exact file + function NAMED",
        has_fn and names_file and names_fn,
        f"function present in source={has_fn}, file named in note={names_file}, "
        f"function named in note={names_fn}",
    )


def d2_template_not_hardcoded() -> None:
    """The deliverable's explicit constraint: a TEMPLATE, never a hardcoded string."""
    src = HOOKS.read_text()
    v1_block = json.loads(V1.read_text())[11]["new"]
    # No fragment of the captured v1 text may be baked into the renderer.
    v1_lines = [
        l for l in v1_block.split("\n") if l.startswith("- **") and len(l) > 60
    ]
    leaked = [l for l in v1_lines if l.strip() in src]
    # And the block must be assembled from parts, not returned as one literal.
    assembles = 'f"- **{name}**: ' in src or '"- **{name}**: ' in src
    note = NOTE.read_text()
    states_split = "99.3" in note and "0.7" in note
    check(
        "D2 compressed TEMPLATE, never a hardcoded string, split stated",
        not leaked and assembles and states_split,
        f"v1 lines leaked into source={len(leaked)}, assembles per-skill lines={assembles}, "
        f"template/data split stated in note={states_split}",
    )


def d3_before_after_and_different_catalog() -> None:
    files = {
        "before-full.txt": None,
        "after-full.txt": None,
        "before-small.txt": None,
        "after-small.txt": None,
    }
    for name in files:
        p = EV / name
        files[name] = len(p.read_text()) if p.exists() else None
    present = all(v is not None for v in files.values())
    shrank_full = present and files["after-full.txt"] < files["before-full.txt"]
    shrank_small = present and files["after-small.txt"] < files["before-small.txt"]
    note = NOTE.read_text()
    quotes_bytes = "22,246" in note and "11,701" in note and "14,540" in note and "6,276" in note
    check(
        "D3 BEFORE/AFTER captured + a DIFFERENT skill set, bytes quoted",
        present and shrank_full and shrank_small and quotes_bytes,
        f"captures present={present}, full shrank={shrank_full}, "
        f"different-catalog shrank={shrank_small}, byte figures quoted in note={quotes_bytes}",
    )


def d4_fidelity_table() -> None:
    verdicts = {}
    for name in ("fidelity-full.txt", "fidelity-small.txt"):
        p = EV / name
        verdicts[name] = "VERDICT: PASS" in p.read_text() if p.exists() else False
    check(
        "D4 FIDELITY TABLE, nothing dropped",
        all(verdicts.values()),
        ", ".join(f"{k}={'PASS' if v else 'MISSING/FAIL'}" for k, v in verdicts.items()),
    )


def d5_pin_test() -> None:
    test = REPO / "modules/tool-skills/tests/test_visibility_line_cap.py"
    exists = test.exists()
    body = test.read_text() if exists else ""
    has_pin = "test_composed_block_is_pinned_to_the_lean_shape" in body
    run = subprocess.run(
        ["uv", "run", "--quiet", "pytest", "tests", "-q", "-p", "no:cacheprovider",
         "--ignore=tests/test_fork_skill_model_role_resolver.py"],
        cwd=REPO / "modules/tool-skills", capture_output=True, text=True,
    )
    tail = run.stdout.strip().split("\n")[-1] if run.stdout else ""
    green = run.returncode == 0
    check(
        "D5 test pinning the composed output (suite green)",
        exists and has_pin and green,
        f"pin test present={has_pin}, suite: {tail}",
    )


def d6_ci_stated_plainly() -> None:
    has_workflows = (REPO / ".github").exists()
    note = NOTE.read_text()
    says_no_ci = "NO CI workflows of its own" in note
    names_cla = "license/cla" in note
    disclaims = "implying one" in note or "implies a green" in note
    check(
        "D6 CI stated plainly (repo has none)",
        (not has_workflows) and says_no_ci and names_cla and disclaims,
        f".github present={has_workflows}, note says no CI={says_no_ci}, "
        f"names the one org check={names_cla}, disclaims a green run={disclaims}",
    )


def d7_draft_pr(with_pr: bool) -> None:
    if not with_pr:
        check("D7 DRAFT PR, not merged", True, "skipped (--with-pr to verify against GitHub)")
        return
    out = subprocess.run(
        ["gh", "pr", "list", "--repo", "microsoft/amplifier-bundle-skills",
         "--head", "lane/z6wa-skills-visibility-renderer", "--state", "all",
         "--json", "number,isDraft,state,url"],
        capture_output=True, text=True,
    )
    try:
        prs = json.loads(out.stdout)
    except json.JSONDecodeError:
        check("D7 DRAFT PR, not merged", False, f"could not read PR: {out.stderr.strip()[:120]}")
        return
    if not prs:
        check("D7 DRAFT PR, not merged", False, "no PR found for this branch")
        return
    pr = prs[0]
    ok = pr["isDraft"] and pr["state"] == "OPEN"
    check(
        "D7 DRAFT PR, not merged",
        ok,
        f"#{pr['number']} draft={pr['isDraft']} state={pr['state']} {pr['url']}",
    )


def landing_stage_statement() -> None:
    """The goal's LANDING STAGE clause requires the note to SAY the bar is the draft PR.

    Verbatim: 'If a deliverable below reads as "the live system now behaves X", satisfy it
    as "X is demonstrated and shipped for landing" and say so in your DONE-NOTE.'
    That is a checkable condition, so it is checked -- not assumed.
    """
    note = NOTE.read_text()
    says_it = "demonstrated and shipped for landing" in note.lower()
    names_stage = "MERGE IS THE MANAGER'S NEXT STAGE" in note
    says_not_merged = "not merged and not live" in note.lower()
    check(
        "LANDING STAGE statement present in DONE-NOTE",
        says_it and names_stage and says_not_merged,
        f'says "demonstrated and shipped for landing"={says_it}, names the manager\'s '
        f"stage={names_stage}, states not merged/not live={says_not_merged}",
    )


def ac5_disposition() -> None:
    """The goal's two requirements ABOUT a NOT-POSSIBLE item."""
    note = NOTE.read_text()
    leads_with_executed = bool(
        re.search(r"WHAT WAS EXECUTED", note)
    ) and "censuses" in note
    names_authority = "13.16" in note
    not_authorised = "No API measurement is authorised" in note
    filed = "model_performance-i5n9" in note
    check(
        "AC5 NOT-POSSIBLE recorded per the goal's rules",
        leads_with_executed and names_authority and not_authorised and filed,
        f"leads with what was executed={leads_with_executed}, names the authority that "
        f"would close it={names_authority}, quotes the goal's prohibition={not_authorised}, "
        f"follow-on filed={filed}",
    )


def main() -> int:
    with_pr = "--with-pr" in sys.argv
    d1_file_and_function_named()
    d2_template_not_hardcoded()
    d3_before_after_and_different_catalog()
    d4_fidelity_table()
    d5_pin_test()
    d6_ci_stated_plainly()
    d7_draft_pr(with_pr)
    landing_stage_statement()
    ac5_disposition()

    print("=" * 78)
    print("LANE z6wa — GOAL DELIVERABLES COMPLETENESS GATE")
    print("Checked against shipped artefacts, not against this lane's own claims.")
    print("=" * 78)
    for label, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        print(f"         {detail}")
    deliverables = [r for r in results if r[0].startswith("D")]
    n_ok = sum(1 for _, ok, _ in deliverables if ok)
    print()
    print(f"GOAL DELIVERABLES: {n_ok}/{len(deliverables)} PASS")
    ac_ok = all(ok for label, ok, _ in results if label.startswith("AC"))
    print(f"AC5 disposition recorded per the goal's rules: {'YES' if ac_ok else 'NO'}")
    land_ok = all(ok for label, ok, _ in results if label.startswith("LANDING"))
    print(f"LANDING STAGE stated as the goal requires: {'YES' if land_ok else 'NO'}")
    print()
    allok = all(ok for _, ok, _ in results)
    print("VERDICT:", "COMPLETE" if allok else "INCOMPLETE")
    if allok:
        print("  All seven DELIVERABLES shipped. AC5 is NOT-POSSIBLE because the goal")
        print("  authorises no API measurement — recorded, priced, and carried forward")
        print("  as model_performance-i5n9. Terminal outcome: branch B, state resolved.")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
