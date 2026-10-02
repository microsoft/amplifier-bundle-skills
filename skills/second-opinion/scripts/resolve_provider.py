#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["click>=8.1,<9"]
# ///
"""Thin Click wrapper for safe second-opinion provider resolution."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Sequence

import click

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from provider_discovery import run_request  # noqa: E402
from provider_resolution import (  # noqa: E402 - legacy import compatibility
    ResolutionError as ResolutionError,
    concrete_model as concrete_model,
    normalize_inventories as normalize_inventories,
    normalize_items as normalize_items,
    resolve_provider as resolve_provider,
    resolve_request as resolve_request,
    resolve_reviewers as resolve_reviewers,
)


def _safe_usage(raw: Sequence[str]) -> tuple[dict[str, Any], int]:
    batch = any(value == "--reviewers-json" or value.startswith("--reviewers-json=") for value in raw)
    return {"ok": False, "code": "usage_error", "message": "Invalid provider selection arguments."}, 2 if batch else 1


class SafeJsonCommand(click.Command):
    """Render parser failures as safe JSON without reflecting selectors."""

    def main(self, *args: Any, standalone_mode: bool = True, **kwargs: Any) -> Any:
        try:
            status = super().main(*args, standalone_mode=False, **kwargs)
        except click.UsageError:
            raw = list(kwargs.get("args", args[0] if args else []) or [])
            payload, status = _safe_usage(raw)
            click.echo(json.dumps(payload, sort_keys=True))
        if isinstance(status, int) and status:
            raise click.exceptions.Exit(status)
        return status


@click.command(cls=SafeJsonCommand, context_settings={"help_option_names": ["--help"]})
@click.option("--id", "config_id", help="Prefer this configured endpoint; discover the label if absent.")
@click.option("--provider", help="Configured provider type; omit --model to use its default.")
@click.option("--model", help="Requested model ID, with equivalent-name and known-version matching.")
@click.option("--request", help="Reviewer/model phrase such as a family, version, or latest family.")
@click.option("--reviewers-json", help="Ordered batch of id, provider, or request selector objects.")
@click.option("--models-json", help="Endpoint-ID mapping to model records (id, source, availability).")
@click.option("--concurrency", type=int, help="Maximum simultaneous reviewers, not inventory probe count.")
@click.option("--cwd", default=None, help="Configuration context directory; defaults to the invoking cwd.")
@click.option("--list-providers", is_flag=True, help="List safe configured endpoint metadata.")
@click.option("--list-models", help="List known models for one configured endpoint with discovery status.")
def cli(**options: Any) -> None:
    """Resolve configured reviewer endpoints without exposing settings or CLI output."""
    payload, status = run_request(**options)
    click.echo(json.dumps(payload, sort_keys=True))
    if status:
        raise click.exceptions.Exit(status)


def main(argv: Sequence[str] | None = None) -> int:
    """Compatibility entry point for existing script callers and tests."""
    try:
        result = cli.main(args=list(sys.argv[1:] if argv is None else argv), prog_name="resolve_provider.py", standalone_mode=False)
        return int(result) if isinstance(result, int) else 0
    except click.exceptions.Exit as error:
        return int(error.exit_code)


if __name__ == "__main__":
    sys.exit(main())
