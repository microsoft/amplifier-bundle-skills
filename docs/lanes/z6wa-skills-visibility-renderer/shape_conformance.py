#!/usr/bin/env python3
"""Does the renderer YIELD THE V1 SHAPE for the v1 session?

`model_performance-z6wa` AC2, second half. "Shape" is not a byte count -- the
goal defines it, in capitals: **"THE TARGET SHAPE IS ONE LINE PER SKILL."**
(GOAL.md:70), and the item description draws the same line explicitly: "a
renderer emits a TEMPLATE plus dynamic content ... the deliverable is a
compressed TEMPLATE that yields the v1 shape for the v1 session, NOT a
hardcoded string."

So shape conformance is a STRUCTURAL predicate over the composed block, and it
is checkable. A block conforms when:

  S1  it opens with the wrapper tag and closes with it
  S2  the regular section header is present, verbatim
  S3  the user-invoked section header is present, verbatim
  S4  section order is regular-then-user-invoked
  S5  EVERY non-template physical line is a skill line matching
      `- **<name>**: <non-empty>`  -- i.e. ONE LINE PER SKILL, no
      continuation lines
  S6  physical line count == skills + template lines exactly (no stragglers)

This script checks the v1 captured text, the stock render, and the lean render
against that predicate, using the SAME skill set for stock and lean.

Usage:
    python3 shape_conformance.py <stock-module-path> <lean-module-path>
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
V1 = Path(
    "/home/bkrabach/dev/openai-evals-team-ci/.amplifier/evaluation/probes/"
    "bji-lean-head/v1_instructions.json"
)

WRAPPER_OPEN = '<system-reminder source="hooks-skills-visibility">'
WRAPPER_CLOSE = "</system-reminder>"
REGULAR_HEADER = "Available skills (use load_skill tool):"
USER_HEADER = "User-invoked skills (available via /command):"
SKILL_LINE = re.compile(r"^- \*\*([^*]+)\*\*(?:: (.+))?$")

_RENDER = r"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
REPO = sys.argv[2]
os.chdir(REPO)
from amplifier_module_tool_skills.discovery import discover_skills
from amplifier_module_tool_skills.hooks import SkillsVisibilityHook
roots = []
cache = Path.home() / ".amplifier" / "cache"
for d in sorted(cache.iterdir()):
    s = d / "skills"
    if s.is_dir():
        roots.append(s)
for e in (Path.home() / ".amplifier" / "skills", Path(REPO) / "skills"):
    if e.is_dir():
        roots.append(e)
catalog = {}
for r in roots:
    try:
        found = discover_skills(r)
    except Exception:
        continue
    for k, v in found.items():
        catalog.setdefault(k, v)
subset = set(json.loads(sys.argv[4]))
catalog = {k: v for k, v in catalog.items() if k in subset}
hook = SkillsVisibilityHook(catalog, json.loads(sys.argv[3]))
print(json.dumps({"block": hook._format_skills_list(catalog), "n": len(catalog)}))
"""


def render(module_path: str, config: dict, subset: list[str]) -> dict:
    out = subprocess.run(
        [sys.executable, "-c", _RENDER, module_path, str(REPO),
         json.dumps(config), json.dumps(subset)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def check_shape(label: str, block: str) -> tuple[bool, list[str]]:
    """Return (conforms, findings)."""
    findings: list[str] = []
    lines = block.split("\n")

    ok_open = lines[0] == WRAPPER_OPEN
    ok_close = lines[-1] == WRAPPER_CLOSE
    findings.append(f"S1 wrapper open/close .......... {'PASS' if ok_open and ok_close else 'FAIL'}")

    ok_reg = REGULAR_HEADER in lines
    findings.append(f"S2 regular header verbatim ..... {'PASS' if ok_reg else 'FAIL'}")
    ok_usr = USER_HEADER in lines
    findings.append(f"S3 user-invoked header verbatim  {'PASS' if ok_usr else 'FAIL'}")

    ok_order = ok_reg and ok_usr and lines.index(REGULAR_HEADER) < lines.index(USER_HEADER)
    findings.append(f"S4 section order ............... {'PASS' if ok_order else 'FAIL'}")

    template_lines = {WRAPPER_OPEN, WRAPPER_CLOSE, REGULAR_HEADER, USER_HEADER, ""}
    strays, skills = [], []
    for line in lines:
        if line in template_lines:
            continue
        m = SKILL_LINE.match(line)
        if m and m.group(2):
            skills.append(m.group(1))
        else:
            strays.append(line)
    ok_lines = not strays
    findings.append(
        f"S5 no text continuation lines .. {'PASS' if ok_lines else 'FAIL'}"
        f"   ({len(skills)} skill lines, {len(strays)} non-blank continuation lines)"
    )
    if strays:
        for s in strays[:3]:
            findings.append(f"      stray: {s[:72]!r}")
        if len(strays) > 3:
            findings.append(f"      ... and {len(strays) - 3} more")

    # Template lines, counted against the v1 target itself (which MUST pass this
    # predicate -- a check that fails its own ground truth is a broken check):
    #   open, regular header, blank, [skills], blank, user header, blank, close
    # = 4 structural + 3 blanks = 7 when both sections are present, 4 + 1 = 5
    # when only one is.
    template_count = 7 if (ok_reg and ok_usr) else 5
    expected = len(skills) + template_count
    surplus = len(lines) - expected
    ok_count = surplus == 0
    findings.append(
        f"S6 ONE LINE PER SKILL, exactly . {'PASS' if ok_count else 'FAIL'}"
        f"   ({len(lines)} physical lines for {len(skills)} skills; surplus {surplus:+d})"
    )
    if surplus:
        findings.append(
            f"      {surplus} physical line(s) beyond one-per-skill + template --"
            " descriptions spilling past their own line"
        )

    conforms = all([ok_open, ok_close, ok_reg, ok_usr, ok_order, ok_lines, ok_count])
    return conforms, findings


def main() -> int:
    stock_path, lean_path = sys.argv[1], sys.argv[2]

    v1_block = json.loads(V1.read_text())[11]["new"].rstrip("\n")
    v1_names = [
        m.group(1) for m in (SKILL_LINE.match(l) for l in v1_block.split("\n")) if m
    ]

    print("=" * 74)
    print('AC2 second half: "the compressed template yields the v1 shape for the v1 session"')
    print('SHAPE, per GOAL.md:70 -- "THE TARGET SHAPE IS ONE LINE PER SKILL."')
    print("=" * 74)

    results = {}
    v1_ok, v1_find = check_shape("v1", v1_block)
    results["v1 captured text (the target)"] = (v1_ok, v1_find, len(v1_block), len(v1_names))

    subset = sorted(set(v1_names))
    stock = render(stock_path, {"visibility_token_budget": 5000}, subset)
    lean = render(lean_path, {}, subset)

    s_ok, s_find = check_shape("stock", stock["block"])
    results["STOCK @HEAD, v1's own skill set"] = (s_ok, s_find, len(stock["block"]), stock["n"])
    l_ok, l_find = check_shape("lean", lean["block"])
    results["THIS CHANGE, v1's own skill set"] = (l_ok, l_find, len(lean["block"]), lean["n"])

    for label, (ok, find, chars, n) in results.items():
        print()
        print(f"--- {label}  ({n} skills, {chars} chars) ---")
        for line in find:
            print("   ", line)
        print(f"    => SHAPE CONFORMS: {'YES' if ok else 'NO'}")

    print()
    print("=" * 74)
    print(f"v1 target shape conforms .......... {'YES' if v1_ok else 'NO'}")
    print(f"STOCK yields the v1 shape ......... {'YES' if s_ok else 'NO'}")
    print(f"THIS CHANGE yields the v1 shape ... {'YES' if l_ok else 'NO'}")
    print()
    print("VERDICT:", end=" ")
    if l_ok and not s_ok:
        print("AC2 second half DONE -- and it is THIS CHANGE that delivers it.")
        print("         Stock did NOT yield the v1 shape; the lean renderer does.")
    elif l_ok:
        print("AC2 second half DONE (stock already conformed).")
    else:
        print("AC2 second half NOT met -- the lean render does not conform.")
    print()
    print("NOTE ON SIZE, which is a DIFFERENT question from shape:")
    print(f"  v1 captured text ............ {len(v1_block)} chars for {len(v1_names)} skills")
    print(f"  stock, same skill set ....... {len(stock['block'])} chars for {stock['n']} skills")
    print(f"  this change, same skill set . {len(lean['block'])} chars for {lean['n']} skills")
    print("  The residual size gap is hand-rewritten DESCRIPTION text (per-session")
    print("  data), not template. No renderer can produce it; that is source-side")
    print("  description tightening. Shape is delivered; size is bounded by data.")
    return 0 if l_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
