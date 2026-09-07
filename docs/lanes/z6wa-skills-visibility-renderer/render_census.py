#!/usr/bin/env python3
"""Render the hooks-skills-visibility block against a real skill catalog.

$0 measurement harness for model_performance-z6wa. Discovers every SKILL.md a
real session would mount (the local bundle cache + user skills + this repo's
own ``skills/``), renders the ``<system-reminder source="hooks-skills-visibility">``
block through the actual renderer, and reports the composed byte size.

READ-ONLY with respect to ~/.amplifier: the cache is enumerated, never written.

Usage:
    python3 docs/lanes/z6wa-skills-visibility-renderer/render_census.py \
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
    """Every skills directory a real session on this host would mount."""
    roots: list[Path] = []
    cache = Path.home() / ".amplifier" / "cache"
    if cache.is_dir():
        for d in sorted(cache.iterdir()):
            s = d / "skills"
            if s.is_dir():
                roots.append(s)
    for extra in (Path.home() / ".amplifier" / "skills", REPO / "skills"):
        if extra.is_dir():
            roots.append(extra)
    return roots


def load_catalog(which: str) -> dict:
    """First-match-wins merge across every discovered source."""
    if which == "small":
        # A deliberately DIFFERENT skill set: this repo's curated skills only.
        roots = [REPO / "skills"]
    else:
        roots = catalog_roots()
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


def render(catalog: dict, config: dict) -> str:
    hook = SkillsVisibilityHook(catalog, config)
    return hook._format_skills_list(catalog)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=None,
                    help="visibility_token_budget; omit for the module default")
    ap.add_argument("--line-cap", type=int, default=None,
                    help="visibility_line_char_cap; omit for the module default")
    ap.add_argument("--catalog", choices=("full", "small"), default="full")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    catalog = load_catalog(args.catalog)
    config: dict = {}
    if args.budget is not None:
        config["visibility_token_budget"] = args.budget
    if args.line_cap is not None:
        config["visibility_line_char_cap"] = args.line_cap

    block = render(catalog, config)
    regular = sum(1 for m in catalog.values() if not m.disable_model_invocation)
    user_inv = sum(1 for m in catalog.values() if m.disable_model_invocation)

    summary = {
        "catalog": args.catalog,
        "skills_total": len(catalog),
        "skills_regular": regular,
        "skills_user_invoked": user_inv,
        "config": config or "<module defaults>",
        "block_chars": len(block),
        "block_lines": block.count("\n") + 1,
        "est_tokens_at_4_59_chars": round(len(block) / 4.59),
    }
    print(json.dumps(summary, indent=2))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(block, encoding="utf-8")
        print(f"\nwrote {len(block)} chars -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
