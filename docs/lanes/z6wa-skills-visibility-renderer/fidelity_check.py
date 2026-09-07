#!/usr/bin/env python3
"""Stock-vs-lean fidelity diff for the hooks-skills-visibility block.

The gate (model_performance-z6wa): list any RULE / CONSTRAINT / COMMAND /
POINTER present in the stock render and absent from the lean one.

For this block the checkable surface is:

  * template-level  -- the wrapper tag, both section headers, and the two
                       command pointers they carry (``load_skill``, ``/command``)
  * coverage        -- every skill name that stock advertised
  * routing signal  -- for each skill whose description carries a trigger
                       phrase, does the RENDERED line still carry one
  * description text-- per-skill byte delta, so nothing is lost silently

Usage:
    python3 fidelity_check.py <stock-module-path> <lean-module-path> [full|small]

Each module path is a directory containing ``amplifier_module_tool_skills``.
Produce a stock copy with:
    git archive HEAD modules/tool-skills | tar -x -C /tmp/stock
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

TRIGGER_RE = re.compile(
    r"\b(use\s+when|use\s+this|use\s+proactively|use\s+for|use\s+at|use\s+it|"
    r"used\s+for|used\s+when|trigger(?:s|ed)?\s+on|always\s+use|"
    r"must\s+be\s+used|do\s+not\s+use|invoke\s+when|reach\s+for)\b",
    re.IGNORECASE,
)

TEMPLATE_ITEMS = {
    "wrapper open tag": '<system-reminder source="hooks-skills-visibility">',
    "wrapper close tag": "</system-reminder>",
    "regular section header": "Available skills (use load_skill tool):",
    "load_skill command pointer": "load_skill",
    "user-invoked section header": "User-invoked skills (available via /command):",
    "/command pointer": "/command",
}

_RENDER = r"""
import json, os, re, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
REPO = sys.argv[2]
os.chdir(REPO)
from amplifier_module_tool_skills.discovery import discover_skills
from amplifier_module_tool_skills.hooks import SkillsVisibilityHook

which = sys.argv[3]
cfg = json.loads(sys.argv[4])
if which == "small":
    roots = [Path(REPO) / "skills"]
else:
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
hook = SkillsVisibilityHook(catalog, cfg)
print(json.dumps({
    "block": hook._format_skills_list(catalog),
    "raw": {n: " ".join((m.description or "").split()) for n, m in catalog.items()},
}))
"""


def render(module_path: str, which: str, config: dict) -> dict:
    out = subprocess.run(
        [sys.executable, "-c", _RENDER, module_path, str(REPO), which, json.dumps(config)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def skill_lines(block: str) -> dict[str, str]:
    return {
        line.split("**")[1]: line
        for line in block.split("\n")
        if line.startswith("- **")
    }


def description_of(line: str) -> str:
    _, _, rest = line.partition("**: ")
    return rest


def main() -> int:
    stock_path, lean_path = sys.argv[1], sys.argv[2]
    which = sys.argv[3] if len(sys.argv) > 3 else "full"

    stock = render(stock_path, which, {"visibility_token_budget": 5000})
    lean = render(lean_path, which, {})

    sb, lb = stock["block"], lean["block"]
    sl, ll = skill_lines(sb), skill_lines(lb)
    raw = stock["raw"]

    print(f"catalog: {which}   skills discovered: {len(raw)}")
    print(f"stock block: {len(sb):>6} chars, {sb.count(chr(10)) + 1:>3} lines")
    print(f"lean  block: {len(lb):>6} chars, {lb.count(chr(10)) + 1:>3} lines")
    print(f"delta      : {len(lb) - len(sb):>6} chars ({100 * (len(lb) - len(sb)) / len(sb):+.1f}%)")
    print()

    print("== 1. TEMPLATE-LEVEL rules / commands / pointers ==")
    dropped_template = []
    for label, needle in TEMPLATE_ITEMS.items():
        in_stock, in_lean = needle in sb, needle in lb
        verdict = "kept" if (in_stock and in_lean) else ("DROPPED" if in_stock else "n/a")
        if verdict == "DROPPED":
            dropped_template.append(label)
        print(f"  {label:<32} stock={in_stock!s:<5} lean={in_lean!s:<5} {verdict}")
    print(f"  -> template items dropped: {len(dropped_template)}")
    print()

    print("== 2. COVERAGE (every advertised skill name) ==")
    missing = sorted(set(sl) - set(ll))
    print(f"  stock names: {len(sl)}   lean names: {len(ll)}   missing from lean: {len(missing)}")
    if missing:
        print(f"  MISSING: {missing}")
    print()

    print("== 3. NAME-ONLY lines (a skill advertised with NO routing signal at all) ==")
    s_bare = sorted(n for n, line in sl.items() if line.endswith("**"))
    l_bare = sorted(n for n, line in ll.items() if line.endswith("**"))
    print(f"  stock: {len(s_bare)}   lean: {len(l_bare)}")
    if l_bare:
        print(f"  lean name-only: {l_bare}")
    print()

    print("== 4. ROUTING TRIGGER retention ==")
    have = sorted(n for n, d in raw.items() if TRIGGER_RE.search(d))
    s_keep = [n for n in have if n in sl and TRIGGER_RE.search(sl[n])]
    l_keep = [n for n in have if n in ll and TRIGGER_RE.search(ll[n])]
    print(f"  descriptions carrying a trigger phrase: {len(have)}")
    print(f"  stock renders keep it: {len(s_keep)}/{len(have)} ({100 * len(s_keep) / len(have):.0f}%)")
    print(f"  lean  renders keep it: {len(l_keep)}/{len(have)} ({100 * len(l_keep) / len(have):.0f}%)")
    regressed = sorted(set(s_keep) - set(l_keep))
    recovered = sorted(set(l_keep) - set(s_keep))
    print(f"  REGRESSED (stock kept, lean lost): {len(regressed)} {regressed}")
    print(f"  recovered (lean kept, stock lost): {len(recovered)}")
    print()

    print("== 5. PER-SKILL description byte delta (top 15 reductions) ==")
    deltas = []
    for name in sorted(sl):
        s_desc = description_of(sl[name])
        l_desc = description_of(ll.get(name, ""))
        if s_desc != l_desc:
            deltas.append((len(l_desc) - len(s_desc), name, len(s_desc), len(l_desc)))
    verbatim = len(sl) - len(deltas)
    print(f"  rendered VERBATIM (byte-identical to stock): {verbatim}/{len(sl)}")
    print(f"  condensed: {len(deltas)}   total description bytes saved: {-sum(d[0] for d in deltas)}")
    for delta, name, s_len, l_len in sorted(deltas)[:15]:
        print(f"    {name:<40} {s_len:>4} -> {l_len:>4}  ({delta:+})")
    print()

    verdict = not dropped_template and not missing and not regressed and len(l_bare) <= len(s_bare)
    print("VERDICT:", "PASS -- no rule/command/pointer/trigger lost" if verdict else "FAIL")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
