---
name: file-ipc-patterns
description: >
  Use when processes need to communicate via the filesystem without a message
  broker — JSONL event logs, atomic state snapshots, async request/response
  via file pairs, or SSE streaming from file tailing.
---

# File-Based IPC & Events

## The Pattern

**Problem:** You have multiple processes (a web server and a container worker, or a host process and a spawned subprocess) that need to exchange messages and stream events. They don't share memory, and you don't want the complexity of a message broker.

**Approach:** Use the filesystem as the message bus. JSON files as request/response pairs, JSONL append-only logs as event streams, and atomic `state.json` snapshots for current status. Bridge async code with `asyncio.Future` objects that resolve when response files appear.

Pattern proven in production across multiple Python CLI tools and web services.

## Key Design Decisions

### 1. JSONL append-only event log + atomic `state.json` snapshot

The EventEmitter writes two complementary files:

- **`events.jsonl`** — append-only, one JSON object per line, flushed immediately so `tail -f` works
- **`state.json`** — atomic overwrite of current status, always a complete snapshot

```python
def emit(self, event_type: str, *, phase=None, data=None) -> None:
    """Append a structured event to events.jsonl. Flushes immediately."""
    record = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
        "instance_id": self._instance_id,
        "event_type": event_type,
        "phase": phase,
        "data": data if data is not None else {},
    }
    line = json.dumps(record, separators=(",", ":")) + "\n"
    with self._lock, (self._work_dir / "events.jsonl").open("a") as fh:
        fh.write(line)
        fh.flush()                              # immediate for tail -f
```

The state snapshot uses atomic write:

```python
def update_state(self, **kwargs) -> None:
    """Overwrite state.json atomically via os.replace."""
    snapshot = {
        "instance_id": self._instance_id,
        "updated_at": datetime.now(UTC).isoformat(),
        **kwargs,
    }
    target = self._work_dir / "state.json"
    fd, tmp_path = tempfile.mkstemp(dir=self._work_dir, prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(snapshot, fh)
        Path(tmp_path).replace(target)          # atomic on POSIX
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise
```

Why two files: `events.jsonl` is the complete history (for replay, debugging, SSE streaming). `state.json` is the current status (for quick reads without scanning the entire log).

### 2. JSON files as cross-process messages (request + response pair)

Input requests use a file-per-request convention:

```python
async def request_input(self, request_id, schema):
    """Write a human-input request file and return a Future for the response."""
    # Validate request_id to prevent path traversal
    safe_name = Path(request_id).name
    if not safe_name or safe_name != request_id:
        raise ValueError(f"Invalid request_id: {request_id!r}")

    input_requests_dir = self._work_dir / "input-requests"
    input_requests_dir.mkdir(parents=True, exist_ok=True)
    request_data = {
        "request_id": request_id,
        "schema": schema,
        "requested_at": datetime.now(UTC).isoformat(),
    }
    request_file = input_requests_dir / f"{safe_name}.json"
    request_file.write_text(json.dumps(request_data, indent=2))

    # Create an asyncio.Future that will be resolved when the response arrives
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    self._pending_futures[request_id] = future
    return future
```

### 3. `asyncio.Future` + file watcher for async request/response

The request creates a Future. When the response arrives (via an API call from the UI), the Future is resolved thread-safely:

```python
def resolve_input_request(self, request_id, payload):
    """Resolve the pending Future for the given request_id."""
    future = self._pending_futures.pop(request_id, None)
    if future is None:
        return
    # Thread-safe: schedule resolution on the Future's event loop
    loop = future.get_loop()
    loop.call_soon_threadsafe(future.set_result, payload)
```

The key detail: `call_soon_threadsafe` is used because the resolve call may come from a different thread (e.g., a sync API handler in a threadpool worker). This schedules the `set_result` on the correct event loop.

### 4. In-memory pub/sub EventBus for SSE delivery

The EventBus routes events to per-instance subscriber queues:

```python
class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, instance_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        self._subscribers.setdefault(instance_id, []).append(queue)
        return queue

    def publish(self, instance_id: str, event: dict | None) -> None:
        for queue in list(self._subscribers.get(instance_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop event rather than block
```

Publishing `None` signals stream completion (sentinel pattern).

### 5. SSE from file tail with incremental reads

The monitor loop mirrors events from a container's filesystem to the host, then publishes to the EventBus:

```python
async def _mirror_events(source_path: Path, dest_path: Path, offset: int) -> int:
    """Mirror new lines from source to dest. Returns new offset."""
    with open(source_path) as f:
        f.seek(offset)
        new_lines = f.readlines()
    if new_lines:
        with open(dest_path, "a") as f:
            f.writelines(new_lines)
    return offset + sum(len(l) for l in new_lines)
```

The SSE endpoint then reads from the host-side file:

```python
@router.get("/instances/{instance_id}/events")
async def stream_events(request, instance_id):
    async def _generate():
        # Wait for file to appear (up to 60s)
        # Incremental read with file position tracking
        # Detect terminal status → close stream
        ...
    return StreamingResponse(_generate(), media_type="text/event-stream")
```

## Template / Starter Code

```python
# events.py — JSONL event log + atomic state + Future-based IPC
import asyncio, contextlib, json, os, tempfile, threading
from datetime import UTC, datetime
from pathlib import Path

class EventEmitter:
    def __init__(self, work_dir: Path, instance_id: str = ""):
        self._work_dir = work_dir
        self._instance_id = instance_id
        self._lock = threading.Lock()
        self._pending: dict[str, asyncio.Future] = {}

    def emit(self, event_type: str, data: dict | None = None) -> None:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "id": self._instance_id,
            "type": event_type,
            "data": data or {},
        }
        line = json.dumps(record, separators=(",", ":")) + "\n"
        with self._lock, (self._work_dir / "events.jsonl").open("a") as fh:
            fh.write(line)
            fh.flush()

    def update_state(self, **kwargs) -> None:
        snapshot = {"id": self._instance_id, "updated_at": datetime.now(UTC).isoformat(), **kwargs}
        target = self._work_dir / "state.json"
        fd, tmp = tempfile.mkstemp(dir=self._work_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(snapshot, fh)
            Path(tmp).replace(target)
        except BaseException:
            with contextlib.suppress(OSError):
                os.close(fd)
            Path(tmp).unlink(missing_ok=True)
            raise

    async def request_input(self, request_id: str, schema: dict) -> asyncio.Future:
        req_dir = self._work_dir / "input-requests"
        req_dir.mkdir(exist_ok=True)
        (req_dir / f"{request_id}.json").write_text(
            json.dumps({"request_id": request_id, "schema": schema, "response": None}))
        self.emit("input_requested", {"request_id": request_id})
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[request_id] = future
        return future

    def resolve_input(self, request_id: str, payload: dict) -> None:
        future = self._pending.pop(request_id, None)
        if future:
            future.get_loop().call_soon_threadsafe(future.set_result, payload)
```

## Gotchas & Lessons Learned

1. **`_pending_futures` is not protected by a lock — intentionally.** `dict.pop()` is effectively atomic under CPython's GIL. This is a deliberate trade-off for simplicity. Warning: Python 3.13+ free-threaded mode removes this guarantee. If you adopt no-GIL Python, add a lock.

2. **Path traversal on request IDs.** The `request_input` method validates that the request_id is a safe filename. Without this, a malicious request_id like `../../etc/evil` could write files outside the intended directory. Always validate IDs used in file path construction.

3. **`fh.flush()` is necessary for `tail -f` to work.** Python's file I/O buffers writes. Without explicit `flush()`, events appear in batches rather than in real-time. The EventEmitter flushes after every line.

4. **Compact JSON for JSONL, pretty JSON for request files.** Events use `separators=(",", ":")` for minimal wire size in high-volume streams. Request files use `indent=2` for human readability during debugging. Match the format to the audience.

5. **The `None` sentinel for stream completion.** The EventBus publishes `None` when a stream is done. Subscribers check for `None` to close their SSE connections cleanly. Without a sentinel, subscribers would hang indefinitely waiting for more events from a completed instance.
