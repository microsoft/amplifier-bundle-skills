"""Resolve a configured Amplifier provider without exposing CLI output."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Sequence

class ResolutionError(Exception):
    """A safe error suitable for JSON output."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

def _fail(code: str, message: str) -> None:
    raise ResolutionError(code, message)

def _concrete_model(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if (
        not value
        or any(char.isspace() for char in value)
        or value == "-"
        or any(char in value for char in "*?[]{}$")
        or (value.startswith("<") and value.endswith(">"))
        or value.lower() in {"model", "default", "placeholder", "none", "null", "unknown"}
    ):
        return None
    return value

def _required_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if type(value) is not str or not value.strip():
        _fail("malformed_schema", "Provider configuration has an invalid schema.")
    return value.strip()

def _normalize_item(item: Any) -> dict[str, Any]:
    if type(item) is not dict:
        _fail("malformed_schema", "Provider configuration has an invalid schema.")
    name = _required_string(item, "name")
    if name.startswith("★ "):
        name = name[2:]
    if not name:
        _fail("malformed_schema", "Provider configuration has an invalid schema.")
    if type(item.get("enabled")) is not bool:
        _fail("malformed_schema", "Provider configuration has an invalid schema.")
    behaviors = item.get("behaviors")
    if type(behaviors) is not list or any(type(value) is not str for value in behaviors):
        _fail("malformed_schema", "Provider configuration has an invalid schema.")
    summary = item.get("config_summary")
    if type(summary) is not dict:
        _fail("malformed_schema", "Provider configuration has an invalid schema.")
    provider_type = _required_string(summary, "type")
    scope = _required_string(summary, "scope")
    _required_string(summary, "priority")
    if "model" not in summary:
        _fail("malformed_schema", "Provider configuration has an invalid schema.")
    default = summary["model"]
    if default in (None, "-"):
        default_model = None
    elif _concrete_model(default) is None:
        _fail("malformed_schema", "Provider configuration has an invalid schema.")
    else:
        default_model = default
    return {
        "id": name,
        "enabled": item["enabled"],
        "provider_type": provider_type,
        "default_model": default_model,
        "scope": scope,
    }


def _normalize_items(items: Any) -> list[dict[str, Any]]:
    if type(items) is not list:
        _fail("malformed_schema", "Provider configuration has an invalid schema.")
    candidates = [_normalize_item(item) for item in items]
    ids = [candidate["id"] for candidate in candidates]
    if len(ids) != len(set(ids)):
        _fail("duplicate_id", "Provider configuration contains duplicate provider ids.")
    return candidates

def _validate_selector(config_id: str | None, provider: str | None, model: str | None) -> str | None:
    if (config_id is None) == (provider is None):
        _fail("invalid_selector", "Specify exactly one provider id or provider type.")
    if config_id is not None and (type(config_id) is not str or not config_id.strip()):
        _fail("invalid_selector", "Provider id must be a non-blank string.")
    if provider is not None and (type(provider) is not str or not provider.strip()):
        _fail("invalid_selector", "Provider type must be a non-blank string.")
    if model is not None and _concrete_model(model) is None:
        _fail("invalid_model", "Model must be a concrete non-blank model name.")
    if provider is not None and model is None:
        _fail("missing_model", "A provider type requires a concrete model.")
    return _concrete_model(model) if model is not None else None

def _resolve_normalized(
    candidates: list[dict[str, Any]],
    *,
    config_id: str | None,
    provider: str | None,
    requested_model: str | None,
) -> dict[str, Any]:
    if config_id is not None:
        matches = [candidate for candidate in candidates if candidate["id"] == config_id.strip()]
        if not matches:
            _fail("unknown_id", "The requested provider id is not configured.")
        selected = matches[0]
        if not selected["enabled"]:
            _fail("disabled_id", "The requested provider id is disabled.")
    else:
        typed = [
            candidate
            for candidate in candidates
            if candidate["enabled"] and candidate["provider_type"] == provider.strip()
        ]
        if not typed:
            _fail("unknown_provider", "No enabled provider has the requested type.")
        matching_default = [
            candidate for candidate in typed if candidate["default_model"] == requested_model
        ]
        if len(matching_default) == 1:
            selected = matching_default[0]
        elif len(matching_default) > 1:
            _fail("ambiguous_provider", "Multiple providers match the requested type and model.")
        elif len(typed) == 1:
            selected = typed[0]
        else:
            _fail("ambiguous_provider", "Multiple providers match the requested type.")

    selected_model = requested_model or selected["default_model"]
    if selected_model is None:
        _fail("missing_model", "The selected provider has no concrete default model.")
    return {
        "ok": True,
        "provider_id": selected["id"],
        "provider_type": selected["provider_type"],
        "model": selected_model,
        "configured_default_model": selected["default_model"],
        "config_scope": selected["scope"],
        "settings_checked": True,
        "mounted_checked": False,
        "execution_verified": False,
    }


def resolve_provider(
    items: Any, *, config_id: str | None = None, provider: str | None = None, model: str | None = None
) -> dict[str, Any]:
    """Select one enabled provider from validated ``provider list`` JSON."""

    requested_model = _validate_selector(config_id, provider, model)
    return _resolve_normalized(
        _normalize_items(items),
        config_id=config_id,
        provider=provider,
        requested_model=requested_model,
    )


def _validate_concurrency(concurrency: Any) -> int:
    if type(concurrency) is not int or concurrency <= 0:
        _fail("invalid_concurrency", "Concurrency must be a positive integer.")
    return concurrency


def _reviewer_entries(reviewers: Any) -> list[Any]:
    if type(reviewers) is not list:
        _fail("invalid_reviewers", "Reviewer list must be a non-empty array.")
    if not reviewers:
        _fail("empty_reviewers", "Reviewer list must not be empty.")
    return reviewers


def _reviewer_selector(reviewer: Any) -> tuple[str | None, str | None, str | None]:
    if type(reviewer) is not dict:
        _fail("invalid_reviewer", "Reviewer entry has an invalid selector.")
    keys = set(reviewer)
    id_keys = {"id"} | ({"model"} if "model" in reviewer else set())
    if keys == id_keys and "id" in reviewer:
        config_id = reviewer["id"]
        provider = None
        model = reviewer.get("model")
        if "model" in reviewer and _concrete_model(model) is None:
            _fail("invalid_model", "Model must be a concrete non-blank model name.")
    elif keys == {"provider", "model"}:
        config_id = None
        provider = reviewer["provider"]
        model = reviewer["model"]
        if _concrete_model(model) is None:
            _fail("invalid_model", "Model must be a concrete non-blank model name.")
    elif keys == {"provider"}:
        config_id = None
        provider = reviewer["provider"]
        model = None
    else:
        _fail("invalid_reviewer", "Reviewer entry has an invalid selector.")
    return config_id, provider, _validate_selector(config_id, provider, model)


def resolve_reviewers(
    items: Any, reviewers: Any, *, concurrency: int = 10
) -> dict[str, Any]:
    """Resolve each reviewer selector against one validated provider list."""

    entries = _reviewer_entries(reviewers)
    checked_concurrency = _validate_concurrency(concurrency)
    candidates = _normalize_items(items)
    rows: list[dict[str, Any]] = []
    resolved: set[tuple[str, str]] = set()

    for index, reviewer in enumerate(entries):
        try:
            config_id, provider, requested_model = _reviewer_selector(reviewer)
            row = _resolve_normalized(
                candidates,
                config_id=config_id,
                provider=provider,
                requested_model=requested_model,
            )
            resolved_key = (row["provider_id"], row["model"])
            if resolved_key in resolved:
                _fail("duplicate_reviewer", "Reviewer resolves to a duplicate provider and model.")
        except ResolutionError as error:
            rows.append(
                {"ok": False, "index": index, "code": error.code, "message": error.message}
            )
        else:
            resolved.add(resolved_key)
            row["index"] = index
            rows.append(row)

    resolved_count = sum(row["ok"] for row in rows)
    return {
        "ok": resolved_count == len(rows),
        "concurrency": checked_concurrency,
        "resolved_count": resolved_count,
        "reviewers": rows,
    }

def _load_items(cwd: str) -> Any:
    command = ["amplifier", "provider", "list", "--format", "json"]
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=30, check=False
        )
    except subprocess.TimeoutExpired:
        _fail("cli_timeout", "Provider configuration command timed out.")
    except FileNotFoundError:
        _fail("cli_missing", "Provider configuration command is unavailable.")
    except (OSError, UnicodeError):
        _fail("cli_failed", "Provider configuration command could not run.")
    if result.returncode != 0:
        _fail("cli_failed", "Provider configuration command failed.")
    try:
        return json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError):
        _fail("invalid_json", "Provider configuration command returned invalid JSON.")

class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ResolutionError("usage_error", "Invalid provider selection arguments.")

def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = _Parser(add_help=False)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--id", dest="config_id")
    selector.add_argument("--provider")
    selector.add_argument("--reviewers-json")
    parser.add_argument("--model")
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--cwd", default=os.getcwd())
    args = parser.parse_args(argv)
    if args.reviewers_json is not None:
        if args.model is not None:
            _fail("usage_error", "Invalid provider selection arguments.")
        try:
            args.reviewers = json.loads(args.reviewers_json)
        except (TypeError, json.JSONDecodeError):
            _fail("invalid_reviewers", "Reviewer list must be valid JSON.")
        _reviewer_entries(args.reviewers)
        args.concurrency = _validate_concurrency(
            10 if args.concurrency is None else args.concurrency
        )
        return args
    if args.concurrency is not None:
        _fail("usage_error", "Invalid provider selection arguments.")
    _validate_selector(args.config_id, args.provider, args.model)
    args.reviewers = None
    return args


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    batch_requested = any(
        argument == "--reviewers-json" or argument.startswith("--reviewers-json=")
        for argument in raw_argv
    )
    try:
        args = _parse_args(raw_argv)
        if args.reviewers is None:
            result = resolve_provider(
                _load_items(args.cwd),
                config_id=args.config_id,
                provider=args.provider,
                model=args.model,
            )
            status = 0 if result["ok"] else 1
        else:
            result = resolve_reviewers(
                _load_items(args.cwd), args.reviewers, concurrency=args.concurrency
            )
            status = 0 if result["ok"] else (2 if result["resolved_count"] == 0 else 1)
    except ResolutionError as error:
        result = {"ok": False, "code": error.code, "message": error.message}
        status = 2 if batch_requested else 1
    print(json.dumps(result, sort_keys=True))
    return status


if __name__ == "__main__":
    sys.exit(main())