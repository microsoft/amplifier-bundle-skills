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

## When this skill is NOT the right answer

This skill assumes a **pure Python CLI** distributed via `uv tool install`. If your project does not fit that profile, use a different pattern:

| Project shape | Use instead |
|--------------|-------------|
| Multi-language stack (Python + Node + Docker) | `one-line-installer-patterns` |
| Raw TS/React app with no Python wrapper | `one-line-installer-patterns` (or publish to npm) |
| Tool that bootstraps system prerequisites | `one-line-installer-patterns` |
| Containerized multi-service app | Ship `docker-compose.yml`; see `container-orchestration-patterns` |
| Single static binary (Go/Rust) | GitHub releases + `curl -L .../bin -o ~/.local/bin/tool` |

If the project IS a pure Python CLI, the rest of this skill applies.

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

### 6. Post-install configuration: `init`, `login`, or nothing?

The Amplifier ecosystem convention for first-run configuration is `<tool> init`. This is **internally consistent** but **not** the dominant community convention. Choose deliberately:

| Tool needs | Recommended subcommand | Examples |
|------------|------------------------|----------|
| Auth/credentials only | `<tool> login` or `<tool> auth login` | gh, vercel, heroku, fly, supabase |
| Tool-wide config (region, defaults) | `<tool> configure` | aws |
| Per-project setup (creates files in cwd) | `<tool> init` | terraform, firebase, npm, cargo |
| Sensible defaults; prompt lazily | (no subcommand) | bun, deno, rustup, pnpm |

In the broader community, `init` overwhelmingly means "create a new project/workspace in the current directory." Using `init` for "configure the tool itself" has essentially one major precedent: `gcloud init`. If you're building a tool the broader community will consume, prefer `login` / `configure` / no-command unless you actually mean "scaffold a new project here." If your audience is internal Amplifier-only, the `init` convention is fine — just know what you're choosing.

See `one-line-installer-patterns` for the full survey table and the rationale.

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

## Related skills

- **`one-line-installer-patterns`** — For projects that can't use `uv tool install`: multi-language stacks, raw TS/React apps, tools that need system bootstrapping, or non-technical audiences. Also contains the full community convention survey for post-install commands referenced in §6 above.
- **`config-state-patterns`** — Where to store the config and state created by your tool's `init` / `configure` / `login` flow.
- **`http-service-patterns`** — If your tool is an HTTP service (FastAPI lifecycle, SPA + API, WebSockets, SSE).
