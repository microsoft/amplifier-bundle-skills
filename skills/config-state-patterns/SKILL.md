---
name: config-state-patterns
description: >
  Use when your tool needs persistent configuration files with safe defaults
  merging, atomic state writes that survive crashes, or conventional file
  locations for config vs state vs secrets.
---

# Configuration & State Management

## The Pattern

**Problem:** Your tool has user-configurable settings (host, port, auth mode) and runtime state (which sessions are active, device heartbeats) that must persist across restarts and handle concurrent reads/writes safely.

**Approach:** Separate config from state. Use a defaults-merge-overlay pattern with known-keys-only filtering for settings. Use atomic writes (write-to-tmp-then-`os.replace`) for state. Use asyncio locks for concurrent access. Follow XDG-conventional paths.

Pattern proven in production across multiple Python CLI tools and web services.

## Key Design Decisions

### 1. Defaults-merge-overlay — never trust the file alone

The settings file might be from an older version (missing new keys) or a newer version (has keys we don't understand). The `load_settings()` pattern handles both:

```python
def load_settings() -> dict:
    result = copy.deepcopy(DEFAULT_SETTINGS)    # start with ALL defaults
    try:
        text = SETTINGS_PATH.read_text()
        data = json.loads(text)
        for key in DEFAULT_SETTINGS:            # only copy KNOWN keys
            if key in data:
                result[key] = data[key]
    except (FileNotFoundError, json.JSONDecodeError):
        pass                                     # corrupt/missing = use defaults
    return result
```

The critical detail: iteration is over `DEFAULT_SETTINGS` keys, not over the file's keys. Unknown keys in the file are silently ignored. This prevents config drift when a user downgrades or when settings are synced between versions.

### 2. Known-keys-only filtering on write

The same principle applies when saving:

```python
def save_settings(data: dict) -> None:
    merged = copy.deepcopy(DEFAULT_SETTINGS)
    for key in DEFAULT_SETTINGS:
        if key in data:
            merged[key] = data[key]
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(merged, indent=2) + "\n")
```

And on patch (partial update):

```python
def patch_settings(patch: dict) -> dict:
    current = load_settings()
    for key in DEFAULT_SETTINGS:
        if key in patch:
            current[key] = patch[key]
```

### 3. Atomic writes — write-to-tmp-then-`os.replace`

State files can be read by other processes at any time. A naive `write_text()` can produce a half-written file if the process crashes mid-write.

The simple pattern:

```python
def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(STATE_PATH) + ".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, STATE_PATH)                 # atomic on POSIX
```

For extra safety (no predictable tmp path, proper cleanup on error), use `tempfile.mkstemp`:

```python
def _write_instance(self, instance_id: str, data: dict) -> None:
    path = self._instance_path(instance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, default=str)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        Path(tmp_path).replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        Path(tmp_path).unlink(missing_ok=True)
        raise
```

### 4. Asyncio lock for concurrent state access

When state is accessed from a poll loop and from API handlers simultaneously, a module-level asyncio lock serializes access:

```python
state_lock: asyncio.Lock = asyncio.Lock()

async def read_state() -> dict:
    async with state_lock:
        return load_state()

async def write_state(state: dict) -> None:
    async with state_lock:
        save_state(state)
```

For threading contexts, use `threading.Lock` per instance with a `defaultdict`:

```python
self._locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)

# Usage — every mutation acquires the per-instance lock:
def update_instance(self, instance_id: str, **changes) -> InstanceStatus | None:
    with self._locks[instance_id]:
        data = self._read_instance(instance_id)
        ...
```

### 5. XDG-conventional paths

```
~/.config/my-tool/settings.json      # config
~/.config/my-tool/password            # secrets (0600)
~/.config/my-tool/secret              # signing key (0600)
~/.local/share/my-tool/state.json     # state
~/.my-tool/                           # all data (alternative)
~/.my-tool/token                      # auth token (0600)
```

A single env var override for the entire data root is useful:

```python
def get_data_root() -> Path:
    env_dir = os.environ.get("MY_TOOL_DATA_DIR")
    root = Path(env_dir) if env_dir else Path.home() / ".my-tool"
    root.mkdir(parents=True, exist_ok=True)
    return root
```

## Template / Starter Code

```python
# settings.py
import copy, json, os
from pathlib import Path

SETTINGS_PATH = Path.home() / ".config" / "my-tool" / "settings.json"

DEFAULT_SETTINGS: dict = {
    "host": "127.0.0.1",
    "port": 8080,
    "log_level": "info",
}

def load_settings() -> dict:
    result = copy.deepcopy(DEFAULT_SETTINGS)
    try:
        data = json.loads(SETTINGS_PATH.read_text())
        for key in DEFAULT_SETTINGS:
            if key in data:
                result[key] = data[key]
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return result

def save_settings(data: dict) -> None:
    merged = copy.deepcopy(DEFAULT_SETTINGS)
    for key in DEFAULT_SETTINGS:
        if key in data:
            merged[key] = data[key]
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(SETTINGS_PATH) + ".tmp")
    tmp.write_text(json.dumps(merged, indent=2) + "\n")
    os.replace(tmp, SETTINGS_PATH)

def patch_settings(patch: dict) -> dict:
    current = load_settings()
    for key in DEFAULT_SETTINGS:
        if key in patch:
            current[key] = patch[key]
    save_settings(current)
    return current
```

```python
# state.py
import asyncio, contextlib, json, os, tempfile
from pathlib import Path

STATE_DIR = Path(os.environ.get("MY_TOOL_DATA_DIR",
                 str(Path.home() / ".local" / "share" / "my-tool")))
STATE_PATH = STATE_DIR / "state.json"
state_lock = asyncio.Lock()

def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"items": {}}

def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE_DIR, suffix=".tmp")
    try:
        os.write(fd, json.dumps(state, indent=2).encode())
        os.close(fd)
        Path(tmp).replace(STATE_PATH)
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        Path(tmp).unlink(missing_ok=True)
        raise

async def read_state() -> dict:
    async with state_lock:
        return load_state()

async def write_state(state: dict) -> None:
    async with state_lock:
        save_state(state)
```

## Gotchas & Lessons Learned

1. **The choices-to-options merge regression.** In one production system, `PATCH /api/settings` with nested objects would wipe secret keys because `GET /api/settings` redacts keys to `""` for security. A naive merge overwrote real keys with empty strings. The fix preserves existing keys by identifier match, with a positional fallback for edits. This is a general hazard: any time you redact fields in a GET response, the PATCH handler must know not to treat redacted values as intentional changes.

2. **`defaultdict(threading.Lock)` leaks memory.** Per-instance locks are never pruned — one Lock (~100 bytes) per instance_id ever seen. This is acceptable for hundreds of instances but would need LRU eviction at scale.

3. **`copy.deepcopy(DEFAULT_SETTINGS)` is critical.** Without it, mutations to the returned dict would modify the module-level constant. This bug is invisible in single-call tests and only surfaces when settings are loaded twice in the same process.

4. **File permissions for secrets: `0o600` after write, not on `open()`.** Write the file first, then `chmod(0o600)`. This avoids the race where another process reads the file between `open()` and `write()`. Also create the parent directory with `0o700`.

5. **JSON indent for human-editable files.** Write `indent=2` for config files. This lets users `cat` or `vim` their settings. State files that are only machine-read can skip indentation for smaller files and faster writes.
