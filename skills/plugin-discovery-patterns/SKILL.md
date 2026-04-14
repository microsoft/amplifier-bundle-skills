---
name: plugin-discovery-patterns
description: >
  Use when making a system extensible with runtime plugin discovery via
  Python entry points, a file-based plugin registry, multi-backend provider
  abstractions, or schema-driven input validation.
---

# Plugin Discovery & Abstractions

## The Pattern

**Problem:** You have a tool that needs to support multiple backends (e.g., GitHub vs a self-hosted git server), load user-installed plugins (custom implementations), and validate dynamically-generated forms against schemas that change based on user actions.

**Approach:** Two-tier plugin discovery (entry points + file-based registry), a frozen dataclass provider abstraction with auto-derived URLs, and schema-driven validation with function-call evaluation.

Pattern proven in production across multiple Python CLI tools and web services.

## Key Design Decisions

### 1. Two-tier plugin discovery: entry points + file-based registry

Plugins are discovered at runtime via `importlib.metadata.entry_points()`:

```python
def load_plugin(name: str) -> object | None:
    """Load a plugin by name via entry_points."""
    try:
        eps = entry_points(group="my_tool.plugins")
        for ep in eps:
            if ep.name == name:
                plugin_class = ep.load()
                return plugin_class()
    except Exception:
        logger.debug("Failed to discover plugin %r", name, exc_info=True)
    return None
```

But there's a second tier: the file-based registry at `~/.config/my-tool/plugins`. This file stores the PEP 508 specs that were used to install each plugin:

```python
def _read_plugins() -> list[str]:
    """Read plugin specs from the config file."""
    path = _get_plugins_config_path()
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
```

Why two tiers? Entry points tell you what's **active** (installed and importable). The config file tells you what **should be** installed. Discrepancies (configured but not active) indicate a reinstall is needed.

### 2. Plugin add/list/remove with discrepancy detection

The `plugin list` command compares both tiers:

```python
def plugin_list():
    configured = _read_plugins()
    active_eps = list(entry_points(group="my_tool.plugins"))
    active_ep_names = [ep.name for ep in active_eps]

    for spec in configured:
        pkg_name = _extract_package_name(spec)
        is_active = any(pkg_name in ep_name or ep_name in pkg_name
                        for ep_name in active_ep_names)
        if is_active:
            print(f"    {ok_mark} {spec}")
        else:
            print(f"    {warn_mark} {spec}")
            print(f"         (configured but not active — run: my-tool upgrade --force)")
```

Adding a plugin writes to the config file AND reinstalls:

```python
def plugin_add(spec: str):
    name = _extract_package_name(spec)
    specs = _read_plugins()
    # Dedup: replace existing entry with same package name
    existing_names = [_extract_package_name(s) for s in specs]
    if name in existing_names:
        idx = existing_names.index(name)
        specs[idx] = spec                   # allows upgrading a pinned spec
    else:
        specs.append(spec)
    _write_plugins(specs)
    _reinstall_with_plugins(specs)          # uv tool install --with ...
```

The `_extract_package_name` function handles PEP 508 specs:

```python
def _extract_package_name(spec: str) -> str:
    """Extract the bare package name from a PEP 508 spec string.
    'my-plugin @ git+https://...' -> 'my-plugin'
    'my-pkg>=1.0' -> 'my-pkg'
    """
    return re.split(r"\s*[@>=<!~]", spec)[0].strip()
```

### 3. Provider abstraction: frozen dataclass with auto-derived API URLs

Encapsulate all provider-specific logic behind a single abstraction:

```python
@dataclass(frozen=True)
class ServiceProvider:
    """Provider-agnostic service configuration. Instances are immutable."""
    kind: str = "default"
    host: str = "api.example.com"
    token_env: str = "API_TOKEN"
    api_base: str = ""            # auto-derived when empty
    scheme: str = "https"
```

> **Note:** If your architecture involves containers with different network routing, add separate `host` and `container_host` fields.

The `__post_init__` method parses scheme from host URLs:

```python
def __post_init__(self) -> None:
    # Parse scheme from host if present (e.g. "http://localhost:10110")
    parsed_scheme, bare_host = self._parse_host(self.host)
    if parsed_scheme:
        object.__setattr__(self, "host", bare_host)
        if self.scheme == "https":
            object.__setattr__(self, "scheme", parsed_scheme)
```

Why `frozen=True`: providers are immutable configuration. You create one per instance and pass it around. No risk of accidental mutation across threads.

Why `object.__setattr__` in `__post_init__`: frozen dataclasses don't allow normal attribute assignment after `__init__`. The `object.__setattr__` bypass is the standard pattern for post-init derived fields on frozen dataclasses.

### 4. Schema-driven validation

A schema validator evaluates declarative check rules against a context:

```python
def _resolve_value(value_ref, context: dict):
    """Resolve a value reference against the context.
    Value references use {"path": "/field_name"} format.
    """
    if isinstance(value_ref, dict) and "path" in value_ref:
        path = value_ref["path"].lstrip("/")
        parts = path.split("/")
        current = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current
    return value_ref
```

Function calls implement validation logic:

```python
def _evaluate_function_call(fc: dict, context: dict) -> bool:
    func_name = fc.get("call")
    args = fc.get("args") or {}
    # Normalize positional list args → named dict args
    if isinstance(args, list):
        args = {"value": args[0]} if args else {}

    if func_name == "required":
        value = _resolve_value(args.get("value"), context)
        return value is not None and value != ""
    if func_name == "regex":
        value = _resolve_value(args.get("value"), context)
        return bool(re.match(args.get("pattern", ""), str(value)))
    # ... length, numeric, email, and, or, not ...
```

Unknown function calls pass by default — this is a deliberate forward-compatibility choice so older validators don't block schemas with newer check functions.

## Template / Starter Code

```python
# plugins.py — two-tier plugin discovery
import re
from importlib.metadata import entry_points
from pathlib import Path

PLUGIN_GROUP = "my_tool.plugins"
PLUGINS_CONFIG = Path.home() / ".config" / "my-tool" / "plugins"

def load_plugin(name: str):
    """Load a plugin by name via entry points."""
    for ep in entry_points(group=PLUGIN_GROUP):
        if ep.name == name:
            return ep.load()()
    return None

def configured_plugins() -> list[str]:
    if not PLUGINS_CONFIG.exists():
        return []
    return [l.strip() for l in PLUGINS_CONFIG.read_text().splitlines()
            if l.strip() and not l.strip().startswith("#")]

def active_plugins() -> list[str]:
    return [ep.name for ep in entry_points(group=PLUGIN_GROUP)]

def check_discrepancies():
    configured = {extract_name(s) for s in configured_plugins()}
    active = set(active_plugins())
    missing = configured - active    # configured but not installed
    orphaned = active - configured   # installed but not in config
    return missing, orphaned

def extract_name(spec: str) -> str:
    return re.split(r"\s*[@>=<!~]", spec)[0].strip()
```

```python
# provider.py — frozen dataclass provider abstraction
from dataclasses import dataclass

@dataclass(frozen=True)
class Provider:
    kind: str = "default"
    host: str = "api.example.com"
    token_env: str = "API_TOKEN"
    scheme: str = "https"

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}"

    @classmethod
    def from_env(cls, prefix: str = "MY_TOOL") -> "Provider":
        import os
        return cls(
            kind=os.environ.get(f"{prefix}_PROVIDER", "default"),
            host=os.environ.get(f"{prefix}_HOST", "api.example.com"),
            token_env=os.environ.get(f"{prefix}_TOKEN_ENV", "API_TOKEN"),
        )
```

```python
# What a plugin looks like (the interface it must implement):
from typing import Protocol

class MyPlugin(Protocol):
    @property
    def name(self) -> str: ...
    def run(self, params: dict) -> dict: ...
```

## Gotchas & Lessons Learned

1. **Entry point discovery is cached per process.** `importlib.metadata.entry_points()` reads from installed package metadata. If you `pip install` a new plugin, you need to restart the process (or reimport) to see it. The `plugin add` command works around this by reinstalling the entire tool and restarting the service.

2. **The fuzzy matching in `plugin list` is intentional.** The check `pkg_name in ep_name or ep_name in pkg_name` handles naming mismatches between pip package names and entry point names (e.g., `my-tool-plugin-foo` vs `foo`). Strict equality would show false "not active" warnings.

3. **`object.__setattr__` on frozen dataclasses is the standard pattern, not a hack.** Python's `dataclasses` module documents this as the way to set derived fields in `__post_init__` on frozen dataclasses. It works because `__post_init__` is called during `__init__`, before the freeze takes effect in the normal `__setattr__` override.

4. **Unknown validation functions pass by default.** The schema validator returns `True` for unrecognized function calls. This is forward-compatible — a schema authored for a newer validator won't block users on an older version. The alternative (fail on unknown functions) would create hard version coupling between schema authors and validator deployments.

5. **The config-file-plus-entry-points split prevents "config drift."** Without the file-based registry, `uv tool install --force` without `--with` flags would silently remove all plugins. The config file remembers what should be installed, and the reinstall function reads it to build the `--with` arguments.
