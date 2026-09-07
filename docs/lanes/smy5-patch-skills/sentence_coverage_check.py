#!/usr/bin/env python3
"""ly85 second-pass fidelity: SENTENCE-level coverage, not token-level.

Why this exists. This lane's first-pass checker (fidelity_check.py) extracts ATOMS --
code spans, URLs, slash commands, identifiers -- plus a short normative-phrase list.
zc6t's checker was token-only. Both share a blind spot that lane smy5-patch-wayfinder
proved is REAL, not theoretical: it found a dropped plain-prose CONSTRAINT in
wayfinder-voice.md ("A good moment conveys or offers one true, useful thing at almost no
attention cost") that zc6t had scored missing_rules: [], because the sentence contained
no token, no code span and no keyword. Restored at +84 chars. Filed as
model_performance-ly85 and flagged URGENT for every lane still applying these artifacts.

So: for every sentence in STOCK, what fraction of its CONTENT words survive anywhere in
LEAN? Below threshold -> flag for hand adjudication. Deterministic, no model, no spend.
"""
from __future__ import annotations

import re
import subprocess
import sys

THRESHOLD = 0.60

STOP = set("""a an the and or but if then than that this these those of to in on at by for with from
as is are was were be been being it its it's their there here we you your our i he she they them
do does did done can could should would may might must will shall not no nor so such only just
about into over under after before while when where which who whom whose what how why all any each
every both few more most other some own same too very s t don now one two three""".split())


def sentences(text: str) -> list[str]:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)          # fenced blocks are atoms' job
    text = re.sub(r"^\s*\|.*\|\s*$", " ", text, flags=re.M)      # table rows likewise
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}|\n(?=[-*#|])", text)
    return [p.strip() for p in parts if len(p.strip()) > 15]


def content_words(s: str) -> list[str]:
    s = s.replace("\u2019", "'").replace("\u2014", " ").replace("\u2026", " ")
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_.\-]{1,}", s.lower())
    return [w for w in words if w not in STOP and len(w) > 2]


def coverage(sent: str, lean_words: set[str], lean_flat: str) -> tuple[float, list[str]]:
    cw = content_words(sent)
    if not cw:
        return 1.0, []
    missing = [w for w in cw if w not in lean_words and w not in lean_flat]
    return 1.0 - len(missing) / len(cw), missing


def check(name: str, stock: str, lean: str) -> int:
    lean_words = set(content_words(lean))
    lean_flat = lean.lower()
    print(f"\n=== {name} ===")
    flagged = 0
    for sent in sentences(stock):
        cov, missing = coverage(sent, lean_words, lean_flat)
        if cov < THRESHOLD:
            flagged += 1
            one = " ".join(sent.split())
            print(f"  [cov={cov:.2f}] {one[:160]}")
            print(f"      missing content words: {missing}")
    if not flagged:
        print("  no sentence below threshold — every stock sentence's substance survives in lean")
    return flagged


def load_skill_description(src: str) -> str:
    m = re.search(r'    name = "load_skill"\n    description = """(.*?)"""\n', src, re.S)
    assert m
    return m.group(1)


def git_show(ref: str, path: str) -> str:
    return subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True,
                          check=True).stdout


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    total = 0
    ctx = "context/skills-instructions.md"
    total += check(ctx, git_show(base, ctx), open(ctx, encoding="utf-8").read())
    mod = "modules/tool-skills/amplifier_module_tool_skills/__init__.py"
    total += check("load_skill tool description",
                   load_skill_description(git_show(base, mod)),
                   load_skill_description(open(mod, encoding="utf-8").read()))
    print(f"\nSENTENCES FLAGGED FOR ADJUDICATION: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
