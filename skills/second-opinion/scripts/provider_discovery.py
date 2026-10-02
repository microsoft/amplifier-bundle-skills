"""Stdlib-only configured-provider discovery for the second-opinion resolver.

This module owns local subprocess and optional inventory orchestration.  It has
no Click dependency and is reusable by hosts that need the same safe JSON
contract without invoking the command wrapper.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable

from provider_resolution import (
    ResolutionError,
    concrete_model,
    normalize_inventories,
    normalize_items,
    resolve_provider,
    resolve_request,
    resolve_reviewers,
)


_SAFE_FAILURES = {
    "cli_timeout": "Provider configuration command timed out.",
    "cli_missing": "Provider configuration command is unavailable.",
    "cli_failed": "Provider configuration command could not run.",
    "invalid_json": "Provider configuration command returned invalid JSON.",
}


def _error(code: str) -> None:
    raise ResolutionError(code, _SAFE_FAILURES[code])


def _normal_id(value: str) -> str:
    return value.casefold().strip()


def load_provider_list(cwd: str, *, command_runner: Callable[..., Any] | None = None) -> Any:
    """Load one safe provider-list JSON payload; never surface command output."""
    runner = command_runner or subprocess.run
    try:
        result = runner(
            ["amplifier", "provider", "list", "--format", "json"],
            cwd=cwd, capture_output=True, text=True, timeout=8, check=False,
        )
    except subprocess.TimeoutExpired:
        _error("cli_timeout")
    except FileNotFoundError:
        _error("cli_missing")
    except (OSError, UnicodeError):
        _error("cli_failed")
    if result.returncode != 0:
        _error("cli_failed")
    try:
        return json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError):
        _error("invalid_json")


def _inventory_script() -> Path:
    return Path(__file__).with_name("model_inventory.py")


def _app_interpreter() -> Path | None:
    executable = shutil.which("amplifier")
    if not executable:
        return None
    try:
        first_line = Path(executable).read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except (OSError, IndexError):
        return None
    if not first_line.startswith("#!"):
        return None
    interpreter = Path(first_line[2:].strip().split()[0])
    if (not interpreter.is_absolute() or "python" not in interpreter.name.casefold()
            or not interpreter.is_file() or not os.access(interpreter, os.X_OK)):
        return None
    return interpreter


def probe_inventory(
    provider_id: str, cwd: str, *, command_runner: Callable[..., Any] | None = None
) -> tuple[list[dict[str, Any]], bool]:
    """Probe one endpoint once; false means discovery was unavailable, not empty."""
    script, interpreter = _inventory_script(), _app_interpreter()
    if not script.is_file() or interpreter is None:
        return [], False
    runner = command_runner or subprocess.run
    try:
        result = runner(
            [str(interpreter), str(script), "--provider-id", provider_id],
            cwd=cwd, capture_output=True, text=True, timeout=8, check=False,
        )
        payload = json.loads(result.stdout) if result.returncode == 0 else None
        models = payload.get("models") if isinstance(payload, dict) and payload.get("ok") is True else None
        return (models, True) if isinstance(models, list) else ([], False)
    except (OSError, UnicodeError, subprocess.TimeoutExpired, TypeError, json.JSONDecodeError):
        return [], False


def discover_inventories(
    items: Any, cwd: str, supplied: Any, provider_ids: list[str],
    *, inventory_loader: Callable[[str, str], tuple[list[dict[str, Any]], bool]] | None = None,
) -> tuple[Any, str, list[str]]:
    """Probe all relevant endpoints once, with four concurrent bounded probes."""
    if supplied is not None:
        return supplied, "supplied", []
    candidates = normalize_items(items)
    wanted = {_normal_id(value) for value in provider_ids}
    if not wanted:
        return {}, "not_requested", []
    selected = [candidate for candidate in candidates if candidate["enabled"] and _normal_id(candidate["id"]) in wanted]
    selected.sort(key=lambda candidate: (candidate["priority"], _normal_id(candidate["id"])))
    load = inventory_loader or probe_inventory
    records: dict[str, dict[str, list[dict[str, Any]]]] = {}
    unavailable: list[str] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(load, candidate["id"], cwd): candidate["id"] for candidate in selected}
        for future in as_completed(futures):
            provider_id = futures[future]
            try:
                models, available = future.result()
            except Exception:
                models, available = [], False
            records[provider_id] = {"models": models}
            if not available:
                unavailable.append(provider_id)
    status = "complete" if not unavailable else ("unavailable" if len(unavailable) == len(selected) else "partial")
    return records, status, sorted(unavailable, key=_normal_id)


def _parse_json(value: str | None, code: str) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        raise ResolutionError(code, "Structured input must be valid JSON.")


def _validate_before_load(
    config_id: str | None, provider: str | None, model: str | None,
    request: str | None, reviewers: Any, concurrency: int | None,
) -> None:
    if model is not None and concrete_model(model) is None:
        raise ResolutionError("invalid_model", "Model must be a concrete non-blank model name.")
    for value, code in ((config_id, "Provider id"), (provider, "Provider type"), (request, "Reviewer request")):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ResolutionError("invalid_selector", f"{code} must be a non-blank string.")
    if concurrency is not None and (type(concurrency) is not int or concurrency <= 0):
        raise ResolutionError("invalid_concurrency", "Concurrency must be a positive integer.")
    if reviewers is None:
        return
    if not isinstance(reviewers, list):
        raise ResolutionError("invalid_reviewers", "Reviewer list must be a non-empty array.")
    if not reviewers:
        raise ResolutionError("empty_reviewers", "Reviewer list must not be empty.")
    # Member errors belong to their ordered rows. Global malformed JSON, empty
    # arrays and invalid concurrency fail before I/O, but one malformed reviewer
    # must not discard the other requested reviews.


def _probe_ids(items: Any, config_id: str | None, provider: str | None, model: str | None, request: str | None, reviewers: Any) -> list[str]:
    candidates = normalize_items(items)
    if config_id is not None:
        if any(_normal_id(candidate["id"]) == _normal_id(config_id) for candidate in candidates):
            return [config_id] if model is not None else []
        return [candidate["id"] for candidate in candidates if candidate["enabled"]]
    if provider is not None:
        return [candidate["id"] for candidate in candidates if model is not None and _normal_id(candidate["provider_type"]) == _normal_id(provider)]
    if request is not None:
        if any(_normal_id(candidate["id"]) == _normal_id(request) or _normal_id(candidate["provider_type"]) == _normal_id(request) for candidate in candidates):
            return []
        return [candidate["id"] for candidate in candidates if candidate["enabled"]]
    ids: list[str] = []
    for reviewer in reviewers or []:
        if not isinstance(reviewer, dict) or set(reviewer) not in ({"id"}, {"id", "model"}, {"provider"}, {"provider", "model"}, {"request"}):
            continue
        if any(not isinstance(reviewer[key], str) or not reviewer[key].strip() for key in ("id", "provider", "request") if key in reviewer):
            continue
        if "model" in reviewer and concrete_model(reviewer["model"]) is None:
            continue
        ids.extend(_probe_ids(items, reviewer.get("id"), reviewer.get("provider"), reviewer.get("model"), reviewer.get("request"), None))
    return ids


def _annotate(result: dict[str, Any], status: str, unavailable: list[str]) -> dict[str, Any]:
    result["discovery_status"] = status
    result["inventory_unavailable_provider_ids"] = unavailable
    if result.get("ok") and status in {"partial", "unavailable"}:
        result.setdefault("disclosure", []).append("Some relevant model inventories were unavailable; selection remains unverified.")
    for row in result.get("reviewers", []):
        if row.get("ok"):
            _annotate(row, status, unavailable)
    return result


def _safe_provider_list(items: Any) -> dict[str, Any]:
    return {"ok": True, "providers": [{"id": candidate["id"], "provider_type": candidate["provider_type"], "enabled": candidate["enabled"], "default_model": candidate["default_model"], "priority": ".".join(str(part) for part in candidate["priority"])} for candidate in normalize_items(items)]}


def _safe_model_list(items: Any, config_id: str, cwd: str, supplied: Any, inventory_loader: Any) -> dict[str, Any]:
    candidates = normalize_items(items)
    selected = [candidate for candidate in candidates if _normal_id(candidate["id"]) == _normal_id(config_id)]
    if not selected:
        raise ResolutionError("unknown_id", "The requested provider id is not configured.")
    inventories, status, unavailable = discover_inventories(items, cwd, supplied, [selected[0]["id"]], inventory_loader=inventory_loader)
    return {"ok": True, "provider_id": selected[0]["id"], "models": normalize_inventories(inventories, candidates).get(selected[0]["id"], []), "discovery_status": status, "inventory_unavailable_provider_ids": unavailable}


def run_request(
    *, config_id: str | None = None, provider: str | None = None, model: str | None = None,
    request: str | None = None, reviewers_json: str | None = None, models_json: str | None = None,
    concurrency: int | None = None, cwd: str | None = None, list_providers: bool = False,
    list_models: str | None = None, command_runner: Callable[..., Any] | None = None,
    inventory_loader: Callable[[str, str], tuple[list[dict[str, Any]], bool]] | None = None,
) -> tuple[dict[str, Any], int]:
    """Return safe resolver JSON and its 0/1/2 status without any Click dependency."""
    cwd = cwd or os.getcwd()
    try:
        selectors = sum(value is not None for value in (config_id, provider, request, reviewers_json))
        actions = int(list_providers) + int(list_models is not None)
        if actions > 1:
            raise ResolutionError("usage_error", "Invalid provider selection arguments.")
        if actions and (selectors or model is not None or concurrency is not None):
            raise ResolutionError("usage_error", "Invalid provider selection arguments.")
        if not actions and selectors != 1:
            raise ResolutionError("usage_error", "Invalid provider selection arguments.")
        if (request is not None or reviewers_json is not None) and model is not None:
            raise ResolutionError("usage_error", "Invalid provider selection arguments.")
        if concurrency is not None and reviewers_json is None:
            raise ResolutionError("usage_error", "Invalid provider selection arguments.")
        supplied = _parse_json(models_json, "invalid_inventory")
        reviewers = _parse_json(reviewers_json, "invalid_reviewers") if reviewers_json is not None else None
        if reviewers_json is not None and reviewers is None:
            raise ResolutionError("invalid_reviewers", "Reviewer list must be a non-empty array.")
        _validate_before_load(config_id, provider, model, request, reviewers, concurrency)
        items = load_provider_list(cwd, command_runner=command_runner)
        if list_providers:
            return _safe_provider_list(items), 0
        if list_models is not None:
            return _safe_model_list(items, list_models, cwd, supplied, inventory_loader), 0
        ids = _probe_ids(items, config_id, provider, model, request, reviewers)
        inventories, discovery, unavailable = discover_inventories(items, cwd, supplied, ids, inventory_loader=inventory_loader)
        if reviewers_json is not None:
            result = resolve_reviewers(items, reviewers, concurrency=10 if concurrency is None else concurrency, inventories=inventories)
            return _annotate(result, discovery, unavailable), 0 if result["ok"] else (1 if result["resolved_count"] else 2)
        if request is not None:
            return _annotate(resolve_request(items, request, inventories=inventories), discovery, unavailable), 0
        return _annotate(resolve_provider(items, config_id=config_id, provider=provider, model=model, inventories=inventories), discovery, unavailable), 0
    except ResolutionError as error:
        return {"ok": False, "code": error.code, "message": error.message}, 2 if reviewers_json is not None else 1
