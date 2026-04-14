---
name: cli-packaging-patterns
description: >
  Use when building a new CLI tool that needs one-line install via uv or npm,
  subcommand dispatch with a default action, or 3-tier config resolution
  (CLI flags, config file, hardcoded defaults).
---

# CLI Packaging & Distribution

## The Pattern

**Problem:** You want a CLI tool that installs cleanly from a git URL with zero manual steps — no cloning, no virtual env, no PATH fiddling.

**Approach:** Combine `pyproject.toml` `[project.scripts]` with hatchling build backend, a `__main__.py` dual entry point, and argparse with a default-action subcommand design so `mytool` and `mytool serve` do the same thing.

Pattern proven in production across multiple Python CLI tools and web services.

## Key Design Decisions

### 1. Hatchling + `[project.scripts]` — Not setuptools

Use hatchling as the build backend. The entry point declaration is:

```toml
[project.scripts]
my-tool = "my_tool.cli:main"
```

Why hatchling: simpler than setuptools, no `setup.py`, no `MANIFEST.in`. The `[tool.hatch.build.targets.wheel]` section lets you exclude test files from the published wheel:

```toml
[tool.hatch.build.targets.wheel]
packages = ["my_tool"]
exclude = ["my_tool/tests", "my_tool/frontend/tests"]
```

### 2. `__main__.py` dual entry — `python -m` always works

Include a minimal `__main__.py` so the tool works even when the script entry point isn't on PATH:

```python
# my_tool/__main__.py
"""Allow running as: python -m my_tool"""
from my_tool.cli import main
main()
```

This matters because `uv tool install` creates a wrapper script, but during development or in edge cases, `python -m my_tool` is a reliable fallback. Service management code should use this as a fallback too:

```python
def _resolve_tool_bin() -> str:
    which = shutil.which("my-tool")
    if which:
        return which
    return f"{sys.executable} -m my_tool"
```

### 3. Default action + subcommands — `tool` equals `tool serve`

Use argparse with shared flags on the root parser AND on the `serve` subcommand, so the bare command runs the server:

```python
def main() -> None:
    parser = argparse.ArgumentParser(prog="my-tool", ...)
    _add_serve_flags(parser)              # flags on root parser
    sub = parser.add_subparsers(dest="command")
    serve_parser = sub.add_parser("serve", help="Start the server (default)")
    _add_serve_flags(serve_parser)        # same flags on 'serve' subcommand
```

The dispatch at the bottom falls through to `serve()` when no subcommand is given:

```python
    else:
        serve(host=args.host, port=args.port, ...)
```

### 4. 3-tier config resolution: CLI > file > default

The `serve()` function resolves every setting with the same pattern — CLI flag wins, then settings file, then hardcoded default:

```python
settings = load_settings()
host = host if host is not None else settings.get("host", "127.0.0.1")
port = port if port is not None else settings.get("port", 8088)
log_level = log_level if log_level is not None else settings.get("log_level", "info")
```

Using `None` as the argparse default (not a value like `"127.0.0.1"`) is critical — it distinguishes "user didn't pass a flag" from "user explicitly set it."

### 5. `uv tool install git+https://...` compatibility

No special config needed — hatchling + `[project.scripts]` is all `uv` requires. The install command is:

```bash
uv tool install git+https://github.com/yourorg/your-tool
```

For tools with plugins as extras, the `--with` flag adds plugin packages:

```bash
uv tool install git+https://github.com/yourorg/your-tool \
  --with 'your-plugin @ git+https://github.com/yourorg/your-plugin@main'
```

This can be handled programmatically in a reinstall helper:

```python
cmd = [uv_path, "tool", "install",
       "git+https://github.com/yourorg/your-tool", "--force"]
for spec in plugin_specs:
    cmd.extend(["--with", spec])
```

## Template / Starter Code

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my-tool"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["fastapi>=0.115.0", "uvicorn[standard]>=0.30.0"]

[project.scripts]
my-tool = "my_tool.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["my_tool"]
exclude = ["my_tool/tests"]
```

```python
# my_tool/__main__.py
from my_tool.cli import main
main()
```

```python
# my_tool/cli.py
import argparse, sys

def _add_serve_flags(parser):
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)

def serve(host=None, port=None):
    from my_tool.settings import load_settings
    settings = load_settings()
    host = host if host is not None else settings.get("host", "127.0.0.1")
    port = port if port is not None else settings.get("port", 8080)
    import uvicorn
    from my_tool.app import app
    uvicorn.run(app, host=host, port=port)

def doctor():
    """Run diagnostic checks."""
    print("\033[32m✓\033[0m Python", sys.version.split()[0])
    print("\033[32m✓\033[0m my-tool", __version__)
    # Add your checks here

def main():
    parser = argparse.ArgumentParser(prog="my-tool")
    _add_serve_flags(parser)
    sub = parser.add_subparsers(dest="command")
    serve_p = sub.add_parser("serve")
    _add_serve_flags(serve_p)
    sub.add_parser("doctor")

    args = parser.parse_args()
    if args.command == "doctor":
        doctor()
    else:
        serve(host=args.host, port=args.port)
```

## Gotchas & Lessons Learned

1. **argparse `default=None` is load-bearing.** If you set `default="127.0.0.1"` on the `--host` flag, the 3-tier resolution breaks — you can never tell if the user explicitly passed `--host 127.0.0.1` or if argparse filled it in.

2. **`exclude` in hatch config is about the wheel, not the sdist.** Test files still appear in the source distribution. This is fine — you don't want tests in the installed package, but they should be in the sdist for downstream repackagers.

3. **`uv tool install` builds a wheel in an isolated environment.** If your package has undeclared dependencies (imports something not in `[project.dependencies]`), it will fail at install time, not at import time. Explicitly declare transitive deps that may be missing on clean environments.

4. **Service files need the full PATH.** When systemd or launchd runs your tool, PATH is minimal. Capture `os.environ.get("PATH")` at install time and bake it into the service unit. Without this, subprocesses can't find `docker`, `git`, `tmux`, etc.

5. **The `--force` flag on reinstall matters.** `uv tool install` without `--force` is a no-op if the package is already installed. Upgrade commands must use `--force` to ensure the latest git HEAD is fetched.
