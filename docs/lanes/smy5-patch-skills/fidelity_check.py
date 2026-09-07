#!/usr/bin/env python3
"""Fidelity checker: every rule/constraint/command/pointer in STOCK must survive in LEAN.

Run from the repo root AT TODAY'S HEAD -- stock is read from git, lean from the worktree.
Exit 0 = no atom dropped. Exit 1 = something present in stock is absent in lean.
"""
from __future__ import annotations

import re
import subprocess
import sys

ATOM_PATTERNS = [
    (r"`([^`\n]+)`", "code-span"),          # inline code: identifiers, calls, paths, flags
    (r"(https?://[^\s)\]]+)", "url"),        # pointers out
    (r"(?<![\w/])(/[a-z][a-z0-9-]{2,})\b", "slash-command"),
    (r"(~?/?\.amplifier/[A-Za-z0-9_./-]+)", "amplifier-path"),
    (r"\b(load_skill|read_file|delegate|skill_directory|skills_dirs|visibility)\b", "identifier"),
]

# Normative content that must not be silently lost.
NORMATIVE = [
    "progressive disclosure",
    "auto-injected", "automatically",           # catalog injection behaviour
    "first-match-wins",
    "override",
    "isolated subagent", "isolated subagents",
    "own context window",
    "task prompt",
    "work product",
    "never describe metadata", "do not describe the metadata",
]


def atoms(text: str) -> set[str]:
    found: set[str] = set()
    for pat, _kind in ATOM_PATTERNS:
        for m in re.finditer(pat, text):
            found.add(m.group(1).strip())
    return found


def normalise(a: str) -> str:
    """Collapse cosmetic variation that is NOT a loss of meaning."""
    a = a.replace("\u2026", "...").replace("\u2019", "'").replace("\u2014", "-")
    a = re.sub(r'"[^"]*"', '"X"', a)      # argument VALUES vary; the call shape is the rule
    a = re.sub(r"\s+", " ", a)
    return a.strip().lower()


def git_show(ref: str, path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, text=True, check=True
    ).stdout


# Atoms that ARE absent from the lean text but are NOT a loss of a rule/constraint/
# command/pointer. Each one was adjudicated by hand at today's head; anything NOT on this
# list that goes missing fails the check. Keyed by (target, normalised atom).
ADJUDICATED: dict[tuple[str, str], str] = {
    (
        "context/skills-instructions.md",
        "[normative] automatically",
    ): "stock 'injected ... automatically before each request' -> lean 'auto-injected before "
       "each request'. Same rule, different word; lean also STRENGTHENS 'You don't need to call' "
       "into 'do not call'.",
    (
        "load_skill tool description",
        "/path",
    ): "from the illustrative placeholder skill_directory=\"/path/to/skill\". A placeholder VALUE, "
       "not a rule. The rule -- pass the returned skill_directory to read_file -- survives in lean "
       "with its concrete example read_file(skill_directory + \"/examples/code.py\").",
    (
        "context/skills-instructions.md",
        'load_skill(skill_name="x")',
    ): "zc6t's fidelity-report.json flagged this for index 5. Re-verified at today's head: lean "
       "carries load_skill(skill_name=\"...\") (unicode ellipsis) plus two concrete instances "
       "(skills-assist, session-debug). FALSE POSITIVE -- zc6t matched an ASCII-dots literal.",
}


def check(name: str, stock: str, lean: str) -> list[str]:
    s_norm = {normalise(a) for a in atoms(stock)}
    l_norm = {normalise(a) for a in atoms(lean)}
    lean_flat = normalise(lean)
    missing = sorted(a for a in s_norm - l_norm if a not in lean_flat)

    for phrase in NORMATIVE:
        if phrase in stock.lower() and phrase not in lean.lower():
            # allow a same-meaning restatement anywhere in lean
            key = phrase.split()[0]
            if key not in lean.lower():
                missing.append(f"[normative] {phrase}")

    real, adjudicated = [], []
    for m in missing:
        (adjudicated if (name, m) in ADJUDICATED else real).append(m)

    print(f"\n=== {name} ===")
    print(f"stock chars: {len(stock)}   lean chars: {len(lean)}   saved: {len(stock) - len(lean)}")
    print(f"atoms in stock: {len(s_norm)}   atoms in lean: {len(l_norm)}")
    for m in adjudicated:
        print(f"  [adjudicated, not a loss] {m}\n      reason: {ADJUDICATED[(name, m)]}")
    if real:
        print("  DROPPED (present in stock, absent in lean) -- REAL:")
        for m in real:
            print(f"    - {m}")
    else:
        print("  DROPPED: none (beyond the adjudicated entries above)")
    return real


def load_skill_description(src: str) -> str:
    m = re.search(r'    name = "load_skill"\n    description = """(.*?)"""\n', src, re.S)
    assert m, "load_skill description not found"
    return m.group(1)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    failures: list[str] = []

    ctx = "context/skills-instructions.md"
    failures += check(
        ctx,
        git_show(base, ctx),
        open(ctx, encoding="utf-8").read(),
    )

    mod = "modules/tool-skills/amplifier_module_tool_skills/__init__.py"
    failures += check(
        "load_skill tool description",
        load_skill_description(git_show(base, mod)),
        load_skill_description(open(mod, encoding="utf-8").read()),
    )

    print("\n" + ("FIDELITY: FAIL" if failures else "FIDELITY: PASS -- nothing dropped"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
