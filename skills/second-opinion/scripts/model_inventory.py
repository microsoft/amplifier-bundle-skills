#!/usr/bin/env python3
"""Optional read-only inventory adapter for the installed Amplifier application.

It deliberately uses only the installed application's documented public APIs and
returns IDs only. Configuration values stay in-process and are never serialized.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import inspect
import io
import json
from typing import Any


_SAFE_ERROR = {"ok": False, "code": "inventory_unavailable", "models": []}


def _entry_value(entry: Any, name: str) -> Any:
    return entry.get(name) if isinstance(entry, dict) else getattr(entry, name, None)


def _records(models: Any) -> list[dict[str, str]]:
    if not isinstance(models, (list, tuple)):
        return []
    result, seen = [], set()
    for model in models:
        model_id = getattr(model, "id", None)
        if not isinstance(model_id, str) or not model_id.strip() or any(char.isspace() for char in model_id):
            continue
        key = model_id.casefold()
        if key not in seen:
            seen.add(key)
            # This confirms only that the installed provider publishes this ID;
            # it does not attempt a request and therefore is not availability proof.
            result.append({"id": model_id, "source": "provider_supported", "availability": "unknown"})
    return result


def _models_call(function: Any, module: str, config_manager: Any, config: Any) -> Any:
    """Feature-detect the installed signature without assuming an app version."""
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return None
    kwargs: dict[str, Any] = {}
    if "config_manager" in parameters:
        kwargs["config_manager"] = config_manager
    if "collected_config" in parameters:
        kwargs["collected_config"] = config
    try:
        return function(module, **kwargs)
    except TypeError:
        # Do not retry network/API work; this is only a local signature fallback.
        return None


def inventory(provider_id: str) -> dict[str, Any]:
    if not isinstance(provider_id, str) or not provider_id.strip():
        return dict(_SAFE_ERROR)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            settings_module = importlib.import_module("amplifier_app_cli.lib.settings")
            paths_module = importlib.import_module("amplifier_app_cli.paths")
            loader_module = importlib.import_module("amplifier_app_cli.provider_loader")
            # This is the same factory imported by the installed provider command;
            # it supplies the CLI path policy without setup or provider mutation.
            create_config_manager = getattr(paths_module, "create_config_manager")
            get_models = getattr(loader_module, "get_provider_models")
            if not callable(create_config_manager):
                return dict(_SAFE_ERROR)
            settings = create_config_manager()
            if not isinstance(settings, getattr(settings_module, "AppSettings")):
                return dict(_SAFE_ERROR)
            entries = settings.get_provider_overrides()
        if not isinstance(entries, list) or not callable(get_models):
            return dict(_SAFE_ERROR)
        selected = next(
            (entry for entry in entries if _entry_value(entry, "id") == provider_id),
            None,
        )
        if selected is None:
            # The provider list may surface an exact module value rather than the
            # override id. This is identity fallback, never a family alias.
            selected = next(
                (entry for entry in entries if _entry_value(entry, "module") == provider_id),
                None,
            )
        module, config = _entry_value(selected, "module"), _entry_value(selected, "config")
        if not isinstance(module, str) or not module:
            return dict(_SAFE_ERROR)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            models = _models_call(get_models, module, settings, config)
        return {"ok": True, "models": _records(models)}
    except Exception:
        # Exception text, stdout, and logger output can contain paths/endpoints/tokens.
        return dict(_SAFE_ERROR)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--provider-id")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        print(json.dumps(_SAFE_ERROR, sort_keys=True))
        return 2
    print(json.dumps(inventory(args.provider_id), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
