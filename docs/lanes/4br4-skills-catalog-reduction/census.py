#!/usr/bin/env python3
"""Render the hooks-skills-visibility block with THIS CHECKOUT's skills authoritative.

$0 measurement harness for model_performance-4br4. Same renderer and same host
catalog as the sibling lane's docs/lanes/z6wa-skills-visibility-renderer/render_census.py,
with one deliberate difference: the cached copy of amplifier-bundle-skills is
EXCLUDED and this repo's ``skills/`` is merged FIRST, so a before/after run
measures the branch's edits instead of the cache's stale copy.

READ-ONLY with respect to ~/.amplifier: the cache is enumerated, never written.

Usage:
    python3 docs/lanes/4br4-skills-catalog-reduction/census.py \
        [--budget N] [--catalog full|small] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "modules" / "tool-skills"))

from amplifier_module_tool_skills.discovery import discover_skills  # noqa: E402
from amplifier_module_tool_skills.hooks import SkillsVisibilityHook  # noqa: E402


def catalog_roots() -> list[Path]:
    """Every skills dir a real session on this host mounts, repo copy first.

    Any cached clone of amplifier-bundle-skills is skipped: this checkout is
    the copy under test, and first-match-wins would otherwise let the cache
    mask every edit on the branch.
    """
    roots: list[Path] = [REPO / "skills"]
    cache = Path.home() / ".amplifier" / "cache"
    if cache.is_dir():
        for d in sorted(cache.rglob("skills")):
            if not d.is_dir():
                continue
            sd = str(d)
            if "amplifier-bundle-skills" in sd:
                continue
            if "fixture" in sd or "/tests/" in sd or "/experiments/" in sd:
                continue
            if d.parent == cache:  # ~/.amplifier/cache/skills is a clone root
                continue
            roots.append(d)
    user = Path.home() / ".amplifier" / "skills"
    if user.is_dir():
        roots.append(user)
    return roots


def load_catalog(which: str) -> dict:
    roots = [REPO / "skills"] if which == "small" else catalog_roots()
    merged: dict = {}
    for r in roots:
        try:
            found = discover_skills(r)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! skipped {r}: {exc}", file=sys.stderr)
            continue
        for name, meta in found.items():
            merged.setdefault(name, meta)
    return merged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=2500, help="visibility_token_budget (shipped default 2500)")
    ap.add_argument("--line-cap", type=int, default=None)
    ap.add_argument("--catalog", choices=("full", "small"), default="full")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    catalog = load_catalog(args.catalog)
    config: dict = {"visibility_token_budget": args.budget}
    if args.line_cap is not None:
        config["visibility_line_char_cap"] = args.line_cap

    block = SkillsVisibilityHook(catalog, config)._format_skills_list(catalog)
    regular = sorted(n for n, m in catalog.items() if not m.disable_model_invocation)
    hidden = sorted(n for n, m in catalog.items() if m.disable_model_invocation)

    summary = {
        "catalog": args.catalog,
        "skills_total": len(catalog),
        "skills_regular": len(regular),
        "skills_user_invoked": len(hidden),
        "config": config,
        "block_chars": len(block),
        "block_lines": block.count("\n") + 1,
        "regular_names": regular,
        "user_invoked_names": hidden,
    }
    print(json.dumps(summary, indent=2))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(block, encoding="utf-8")
        print(f"\nwrote {len(block)} chars -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
