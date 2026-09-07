#!/usr/bin/env python3
"""Score the clean-room arm outputs against the shipped skill-description checks.

Applies the same three checks `skill_description_check.py` applies -- length
(WARNING >400, ERROR >800), `<example>`, `<commentary>` -- to the emitted
`*.SKILL.md.txt` files under `evidence/creation-skill-demo/{shipped,patched}/`.

The arm outputs are named `*.SKILL.md.txt` and NOT `SKILL.md` on purpose: the
validator scans `docs/` (it says so in its own comment), so an evidence file
literally named `SKILL.md` would be counted as a shipped skill of this repo and
would pollute the repo-level before/after counts.

Usage:
    python3 measure_arms.py <evidence/creation-skill-demo dir>
"""

import re
import statistics
import sys
from pathlib import Path

import yaml

WARN, ERROR = 400, 800
FRONTMATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n", re.DOTALL)

base = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

rows = []
for arm in ("shipped", "patched"):
    for f in sorted((base / arm).glob("*.SKILL.md.txt")):
        text = f.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        if not match:
            rows.append((arm, f.name, None, "NO_FRONTMATTER", 0, 0))
            continue
        desc = (yaml.safe_load(match.group(1)) or {}).get("description", "")
        n = len(desc)
        verdict = "ERROR" if n > ERROR else ("WARNING" if n > WARN else "clean")
        rows.append(
            (
                arm,
                f.name,
                n,
                verdict,
                len(re.findall(r"<example>", desc, re.IGNORECASE)),
                desc.lower().count("<commentary>"),
            )
        )

if not rows:
    print(f"no arm outputs found under {base}")
    raise SystemExit(1)

w = max(len(r[1]) for r in rows)
print(f"{'arm':8} {'file':{w}} {'chars':>6}  verdict   <example>  <commentary>")
for r in rows:
    print(f"{r[0]:8} {r[1]:{w}} {str(r[2]):>6}  {r[3]:8}  {r[4]:^9}  {r[5]:^11}")

print()
print(f"{'arm':8} {'creation skill':20} {'n':>2}  {'mean':>5}  {'chars':<34} over-cap")
for arm in ("shipped", "patched"):
    for skill, creator in (("rotate-staging-key", "skillify"), ("rollback-warden", "personafy")):
        cell = [r for r in rows if r[0] == arm and r[1].startswith(skill)]
        if not cell:
            continue
        lengths = [r[2] for r in cell]
        over = sum(1 for r in cell if r[3] != "clean")
        print(
            f"{arm:8} {creator:20} {len(cell):>2}  {statistics.mean(lengths):>5.0f}  "
            f"{str(lengths):<34} {over}/{len(cell)}"
        )

print()
bad = [r for r in rows if r[0] == "patched" and (r[3] != "clean" or r[4] or r[5])]
print(f"PATCHED ARM: {len(bad)} finding(s) across {sum(1 for r in rows if r[0] == 'patched')} outputs")
