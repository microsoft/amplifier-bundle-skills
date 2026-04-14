---
name: self-managing-tool-patterns
description: >
  Use when adding a doctor diagnostic command, self-update/upgrade mechanism,
  cross-platform service installation (systemd and launchd), or post-upgrade
  verification to a CLI tool.
---

# Self-Managing Tool Lifecycle

## The Pattern

**Problem:** Your tool runs as a long-lived service. Users need to check if it's healthy, upgrade it without SSH'ing in, and have it start on boot. You need this to work on both Linux (systemd) and macOS (launchd).

**Approach:** A `doctor` command for diagnostics, PEP 610 introspection for install source detection, an `upgrade` flow that stops-reinstalls-regenerates-restarts-verifies, and cross-platform service management with PATH forwarding.

Pattern proven in production across multiple Python CLI tools and web services.

## Key Design Decisions

### 1. Doctor — structured checklist with colored output

Implement a `doctor` command that checks prerequisites, versions, service status, and update availability:

```python
def doctor() -> None:
    ok_mark = "\033[32m\u2713\033[0m"    # green check
    fail_mark = "\033[31m\u2717\033[0m"  # red x
    warn_mark = "\033[33m!\033[0m"       # yellow warning
```

The checklist should cover:
- Python version (3.11+ required)
- External dependencies (docker, git, etc.)
- Tool version + install source + update check
- Settings file existence
- Serve configuration
- TLS certificate status and expiry (if applicable)
- Auth status (if applicable)
- Active sessions/instances
- Platform + service status

The service status check should be platform-aware:

```python
if sys.platform == "darwin":
    plist = Path.home() / "Library" / "LaunchAgents" / "com.my-tool.plist"
    if plist.exists():
        result = subprocess.run(
            ["launchctl", "print", f"gui/{uid}/com.my-tool"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"  {ok_mark} Service: launchd agent running")
else:
    systemd_user = Path.home() / ".config" / "systemd" / "user" / "my-tool.service"
    if systemd_user.exists():
        print(f"  {ok_mark} Service: systemd user unit installed")
```

### 2. PEP 610 install source detection via `direct_url.json`

Detect how the tool was installed to determine the correct upgrade strategy:

```python
def _get_install_info() -> dict:
    """Detect how the tool was installed using PEP 610 direct_url.json."""
    dist = distribution("my-tool")
    info["version"] = dist.metadata["Version"]
    du_text = dist.read_text("direct_url.json")
    if du_text:
        du = json.loads(du_text)
        if "vcs_info" in du:
            info["source"] = "git"
            info["commit"] = du["vcs_info"].get("commit_id", "")
            info["url"] = du.get("url", "")
        elif "dir_info" in du and du["dir_info"].get("editable"):
            info["source"] = "editable"
        else:
            info["source"] = "unknown"
    else:
        info["source"] = "pypi"  # No direct_url.json → probably PyPI
```

Update checking uses the install source:

```python
def _check_for_update(info) -> tuple[bool, str]:
    if info["source"] == "editable":
        return False, "editable install — manage updates manually"
    if info["source"] == "git":
        # Compare installed commit_id against remote HEAD sha
        result = subprocess.run(["git", "ls-remote", info["url"], "HEAD"], ...)
        remote_sha = result.stdout.strip().split()[0]
        if local_sha == remote_sha:
            return False, f"up to date (commit {local_sha[:8]})"
        return True, f"update available ({local_sha[:8]} → {remote_sha[:8]})"
    if info["source"] == "pypi":
        # Compare against PyPI JSON API
        ...
```

### 3. Upgrade flow: stop > reinstall > regenerate service > restart > verify

The upgrade sequence is strict and ordered:

```python
def upgrade(force=False):
    # 1. Check if update is available (skip if --force)
    # 2. Stop the running service
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{label}"])
    # 3. Reinstall from source
    subprocess.run([uv_path, "tool", "install",
                    "git+https://...", "--force"])
    # 4. Regenerate service file (picks up new binary path)
    service_install()
    # 5. Restart service
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)])
    # 6. Verify with doctor
    doctor()
```

For tools with plugins, include them during reinstall:

```python
# Include --with for each configured plugin
specs = _read_plugins()
with_args = []
for spec in specs:
    with_args.extend(["--with", spec])
cmd = [uv_path, "tool", "install",
       "git+https://github.com/yourorg/your-tool",
       "--force", *with_args]
```

### 4. Cross-platform service management

Generate platform-specific service files from templates with PATH forwarding:

**Linux (systemd user unit):**

```python
_SYSTEMD_UNIT_TEMPLATE = """\
[Unit]
Description=my-tool
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5s
Environment=PATH={safe_path}

[Install]
WantedBy=default.target
"""
```

**macOS (launchd plist):**

```python
_LAUNCHD_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
...
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{safe_path}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
"""
```

The install function captures the current PATH:

```python
def _systemd_install() -> None:
    tool_bin = _resolve_tool_bin()
    safe_path = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    exec_start = f"{tool_bin} serve"
    unit_content = _SYSTEMD_UNIT_TEMPLATE.format(
        exec_start=exec_start, safe_path=safe_path)
    _SYSTEMD_UNIT_DIR.mkdir(parents=True, exist_ok=True)
    _SYSTEMD_UNIT_PATH.write_text(unit_content)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "my-tool"], check=True)
```

### 5. Public dispatch API

The service module exposes a platform-dispatching public API:

```python
def service_install():
    if _is_darwin(): _launchd_install()
    else: _systemd_install()

def service_uninstall():
    if _is_darwin(): _launchd_uninstall()
    else: _systemd_uninstall()

# ... start, stop, restart, status, logs ...
```

## Template / Starter Code

```python
# lifecycle.py — doctor + install info + service management
import json, os, platform, shutil, subprocess, sys
from importlib.metadata import distribution, PackageNotFoundError
from pathlib import Path

PACKAGE_NAME = "my-tool"

def get_install_info() -> dict:
    info = {"source": "unknown", "version": "0.0.0", "commit": None, "url": None}
    try:
        dist = distribution(PACKAGE_NAME)
        info["version"] = dist.metadata["Version"]
        du_text = dist.read_text("direct_url.json")
        if du_text:
            du = json.loads(du_text)
            if "vcs_info" in du:
                info["source"] = "git"
                info["commit"] = du["vcs_info"].get("commit_id", "")
                info["url"] = du.get("url", "")
            elif du.get("dir_info", {}).get("editable"):
                info["source"] = "editable"
        else:
            info["source"] = "pypi"
    except PackageNotFoundError:
        pass
    return info

def doctor():
    ok = "\033[32m\u2713\033[0m"
    fail = "\033[31m\u2717\033[0m"
    warn = "\033[33m!\033[0m"

    info = get_install_info()
    print(f"  {ok} {PACKAGE_NAME} {info['version']} (via {info['source']})")

    for dep in ["docker", "git"]:
        if shutil.which(dep):
            print(f"  {ok} {dep}")
        else:
            print(f"  {fail} {dep} — not found")
```

## Gotchas & Lessons Learned

1. **PATH forwarding is mandatory for service files.** systemd and launchd run with minimal PATH (`/usr/bin:/bin`). If your tool shells out to `docker`, `git`, etc., they won't be found unless you bake PATH into the service file. Capture the installer's PATH at `service install` time. The `doctor` command helps diagnose this.

2. **launchd uses `bootstrap`/`bootout`, not `load`/`unload`.** The older `launchctl load` is deprecated. Use the newer `bootstrap`/`bootout` API with a `gui/{uid}` domain. Keep a fallback to `load` for older macOS versions.

3. **The upgrade must regenerate the service file.** After reinstalling, the binary path may have changed (new venv, new tool directory). The regenerate step ensures the service file points to the current binary. Without this, the service starts the old binary after upgrade.

4. **Editable installs should skip upgrade.** Return `(False, "editable install")` for editable installs. Upgrading an editable install via `uv tool install --force` would overwrite the dev checkout with a release build — almost certainly not what the developer intended.

5. **Doctor as post-upgrade verification.** The last step of the upgrade flow is `doctor()`. This catches issues immediately — wrong PATH in service file, missing dependency after upgrade, failed service start — instead of waiting for the user to discover them.

6. **No rollback on failed upgrade.** If reinstall fails mid-upgrade, the service is stopped and the old binary is gone. Neither project implements rollback. For critical deployments, consider snapshotting the venv before `uv tool install --force`.
