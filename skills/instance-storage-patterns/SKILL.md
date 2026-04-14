---
name: instance-storage-patterns
description: >
  Use when your system manages multiple concurrent instances or sessions that
  each need isolated storage directories, per-instance file locking, or a
  prepare-once/create-many session factory pattern.
---

# Instance Storage & Sessions

## The Pattern

**Problem:** You run multiple instances of something (task runners, user sessions, build jobs). Each needs isolated storage, lifecycle tracking, and its own subdirectory tree. You also have expensive initialization (loading bundles, connecting to APIs) that should happen once, not per instance.

**Approach:** A filesystem-backed instance store with per-instance directories, per-instance file locking, and a session factory that prepares once and creates many.

Pattern proven in production across multiple Python CLI tools and web services.

## Key Design Decisions

### 1. Instance-rooted directory layout

All data for a single instance lives under one directory. Example layout (adapt to your needs):

```
~/.my-tool/
  instances/{instance_id}/
    instance.json         — lifecycle metadata (status, timestamps)
    workspace/            — code, git repo, tests
    logs/                 — pipeline node logs, checkpoint.json
    events/               — events.jsonl, state.json, input-requests/
    sidecar-data/         — sidecar service data (databases, repos)
    output/               — artifacts (branch_name.txt, pr_url.txt)
```

This is defined as:

```python
def get_instance_dir(instance_id: str) -> Path:
    d = get_data_root() / "instances" / instance_id
    d.mkdir(parents=True, exist_ok=True)
    return d

# Subdirectory names used by other modules:
WORKSPACE_DIR = "workspace"
LOGS_DIR = "logs"
EVENTS_DIR = "events"
```

The design choice of instance-rooted (not type-rooted) matters: you can `ls`, `tar`, or `rm -rf` one instance directory to inspect, archive, or delete everything about that instance. Compare to the alternative where workspace files live in `workspaces/{id}/` and logs in `logs/{id}/` — that's harder to reason about.

### 2. Single env var override for all data paths

```python
def get_data_root() -> Path:
    env_dir = os.environ.get("MY_TOOL_DATA_DIR")
    root = Path(env_dir) if env_dir else Path.home() / ".my-tool"
    root.mkdir(parents=True, exist_ok=True)
    return root
```

One env var redirects ALL instance data. This is critical for:
- **Testing** — point to a temp directory per test
- **Docker** — mount a host volume at a known path
- **Multi-tenant** — separate data by project

### 3. Per-instance file locking with `defaultdict(threading.Lock)`

The InstanceStore uses a per-instance lock to prevent concurrent writes to the same instance's JSON:

```python
class InstanceStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        # Note: locks are never pruned — one Lock (~100 bytes) per instance_id seen.
        self._locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)

    def create_instance(self, instance_id, name, params) -> dict:
        with self._locks[instance_id]:
            ...

    def update_instance(self, instance_id, **changes) -> dict | None:
        with self._locks[instance_id]:
            data = self._read_instance(instance_id)
            ...
```

Why `defaultdict` instead of a single global lock: a global lock would serialize ALL instance writes. Per-instance locks allow concurrent writes to different instances while serializing writes to the same instance.

### 4. Atomic writes with `tempfile.mkstemp` + `os.replace`

Every instance mutation is written atomically:

```python
def _write_instance(self, instance_id, data):
    path = self._instance_path(instance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, default=str)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        Path(tmp_path).replace(path)        # atomic
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        Path(tmp_path).unlink(missing_ok=True)
        raise
```

Note `BaseException` (not `Exception`) in the except clause — this catches `KeyboardInterrupt` too, preventing orphaned temp files even during Ctrl+C.

### 5. Factory pattern for expensive initialization

If creating instances requires expensive setup (loading configs, preparing templates, compiling schemas), separate the one-time preparation from per-instance creation. Keep the prepared state as a singleton; create lightweight session objects on demand.

### 6. Factory functions for state objects

When your state has nested dicts or lists, always use factory functions that return fresh copies — never share mutable defaults.

```python
def empty_instance() -> dict:
    """Each call returns an independent object — no shared mutables."""
    return {"status": "pending", "created_at": None, "metadata": {}}
```

## Template / Starter Code

```python
# storage.py — filesystem-backed instance store
from collections import defaultdict
import contextlib, json, os, tempfile, threading
from pathlib import Path

class InstanceStore:
    def __init__(self, root: Path):
        self._root = root
        self._locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)

    def _path(self, instance_id: str) -> Path:
        return self._root / "instances" / instance_id / "instance.json"

    def _read(self, instance_id: str) -> dict | None:
        path = self._path(instance_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def _write(self, instance_id: str, data: dict) -> None:
        path = self._path(instance_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            os.write(fd, json.dumps(data, default=str).encode())
            os.close(fd)
            Path(tmp).replace(path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.close(fd)
            Path(tmp).unlink(missing_ok=True)
            raise

    def create(self, instance_id: str, **kwargs) -> dict:
        with self._locks[instance_id]:
            from datetime import UTC, datetime
            now = datetime.now(UTC).isoformat()
            data = {"instance_id": instance_id, "status": "starting",
                    "created_at": now, "updated_at": now, **kwargs}
            self._write(instance_id, data)
            return data

    def update(self, instance_id: str, **changes) -> dict | None:
        with self._locks[instance_id]:
            data = self._read(instance_id)
            if data is None:
                return None
            data.update(changes)
            from datetime import UTC, datetime
            data["updated_at"] = datetime.now(UTC).isoformat()
            self._write(instance_id, data)
            return data

    def list_all(self) -> list[dict]:
        instances_dir = self._root / "instances"
        if not instances_dir.exists():
            return []
        results = []
        for d in instances_dir.iterdir():
            if d.is_dir():
                data = self._read(d.name)
                if data:
                    results.append(data)
        results.sort(key=lambda i: i.get("created_at", ""), reverse=True)
        return results

    def delete(self, instance_id: str) -> bool:
        with self._locks[instance_id]:
            path = self._root / "instances" / instance_id / "instance.json"
            if not path.exists():
                return False
            import shutil
            shutil.rmtree(self._root / "instances" / instance_id)
            return True
```

## Gotchas & Lessons Learned

1. **Instance-rooted vs type-rooted directory layout.** An earlier version used type-rooted paths (`workspaces/{id}`, `logs/{id}`). This was refactored to instance-rooted because: (a) deleting an instance required knowing all the type directories, (b) inspecting an instance required looking in 5+ directories, (c) archiving required a multi-path tar command.

2. **`defaultdict(threading.Lock)` memory note.** Locks are never pruned. Each Lock is ~100 bytes. For hundreds of instances this is negligible. For millions, you'd need an LRU eviction strategy.

3. **`ensure_ascii=False` in JSON dumps.** Use `ensure_ascii=False` so that non-ASCII text (e.g., issue titles in languages other than English) is stored as-is rather than escaped to `\uXXXX`. This makes the JSON files human-readable and reduces file size.

4. **`default=str` as a JSON serialization escape hatch.** Using `json.dumps(data, default=str)` ensures that datetime objects, Paths, and enums serialize without crashing. It's a pragmatic choice for internal storage — you're trading strict type safety for crash resilience.

5. **`mkdir(parents=True, exist_ok=True)` on every write.** Both the store's `_write` and `get_instance_dir` create directories on every call. This seems wasteful but prevents a class of bugs where a directory was deleted between creation and use (e.g., during cleanup or testing). The `exist_ok=True` flag makes repeated calls cheap.
