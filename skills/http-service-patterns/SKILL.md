---
name: http-service-patterns
description: >
  Use when building an HTTP service with FastAPI lifecycle management,
  background poll loops, SPA static file serving with API reverse proxy,
  bidirectional WebSocket relay, or SSE event streaming.
---

# HTTP Services & Proxies

## The Pattern

**Problem:** You need a web service that does more than serve requests — it has a background loop reconciling state, it proxies WebSocket connections to a backend process, and it must start reliably even when the previous instance didn't exit cleanly.

**Approach:** FastAPI `lifespan` for startup/shutdown, `asyncio.create_task` for background loops, bidirectional WebSocket relay for proxying, and pre-bind port cleanup to prevent systemd crash-loops.

Pattern proven in production across multiple Python CLI tools and web services.

## Key Design Decisions

### 1. Pre-bind port cleanup — preventing the restart crash-loop

When systemd restarts a service, the old process may still hold the port in TIME_WAIT. The new process fails to bind, exits with status=1, systemd restarts it, repeat. In one production deployment, 2,075+ systemd restarts occurred before manual intervention.

The fix runs before `uvicorn.run()`:

```python
def _kill_stale_port_holder(port: int) -> None:
    """Kill any existing process on *port* to prevent EADDRINUSE crash-loops."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            my_pid = os.getpid()
            for pid_str in result.stdout.strip().split("\n"):
                pid = int(pid_str.strip())
                if pid != my_pid:
                    os.kill(pid, signal.SIGTERM)
            time.sleep(1)  # Brief wait for the port to be released
    except Exception:
        pass  # lsof not available — proceed; uvicorn will fail naturally
```

Called right before server start:

```python
_kill_stale_port_holder(port)
```

### 2. FastAPI lifespan with background poll loop

Use the FastAPI `lifespan` pattern to start background tasks at startup and clean them up at shutdown.

Starting a poll loop and an httpx client:

```python
async def lifespan(app: FastAPI):
    global _poll_task, _http_client
    await kill_orphan_processes()
    _poll_task = asyncio.create_task(_poll_loop())
    _http_client = httpx.AsyncClient(verify=False)
    app.state.http_client = _http_client
    yield
    # Shutdown
    _poll_task.cancel()
    await _http_client.aclose()
```

Starting both a monitor loop and a watchdog loop:

```python
# Example: dual-loop lifespan for services that need both monitoring and maintenance
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    client = await _try_create_client()     # graceful degradation if unavailable
    app.state.orchestrator = Orchestrator(client=client)
    monitor_instance = asyncio.create_task(monitor_loop(app))
    watchdog_instance = asyncio.create_task(
        app.state.orchestrator.watchdog_loop(app.state.instance_store))
    try:
        yield
    finally:
        watchdog_instance.cancel()
        monitor_instance.cancel()
        if client is not None:
            await client.shutdown()
```

### 3. Bidirectional WebSocket relay with auth + auto-spawn

When proxying browser WebSocket connections to a backend process, check auth and verify the backend is alive BEFORE accepting the browser WS:

```python
@app.websocket("/terminal/ws")
async def terminal_ws_proxy(websocket: WebSocket) -> None:
    # Auth check BEFORE accept — middleware doesn't cover WebSocket scope
    if not await _ws_auth_check(websocket):
        return

    # Ensure backend is reachable BEFORE accepting the browser WS
    if not _is_backend_alive():
        # Auto-spawn backend, wait for it to bind
        ...

    await websocket.accept(subprotocol="tty")

    async with websockets.connect(
        f"ws://localhost:{BACKEND_PORT}/ws",
        subprotocols=[Subprotocol("tty")]
    ) as backend_ws:
        # Two concurrent tasks: client→backend and backend→client
        async def client_to_backend():
            while True:
                msg = await websocket.receive()
                if msg.get("bytes"):
                    await backend_ws.send(msg["bytes"])
                elif msg.get("text"):
                    await backend_ws.send(msg["text"])

        async def backend_to_client():
            async for message in backend_ws:
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_text(message)

        # Run both directions concurrently, cancel on first completion
        done, pending = await asyncio.wait(
            [asyncio.create_task(client_to_backend()),
             asyncio.create_task(backend_to_client())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
```

> **Note:** The subprotocol value (`"tty"` in this example) should match your backend's WebSocket protocol.

### 4. SSE streaming from file tailing

Stream events to the browser using Server-Sent Events read from a JSONL file:

```python
@router.get("/instances/{instance_id}/events")
async def stream_events(request, instance_id) -> StreamingResponse:
    async def _generate():
        # Wait for events file to appear (container may be starting)
        events_path = get_instance_dir(instance_id) / EVENTS_DIR / "events.jsonl"
        for _ in range(60):
            if events_path.exists():
                break
            await asyncio.sleep(1)

        # Incremental read: track file position between polls
        with open(events_path) as fh:
            while True:
                line = fh.readline()
                if line:
                    yield f"data: {line}\n\n"
                else:
                    # Check if instance is in terminal state → close stream
                    instance = store.get_instance(instance_id)
                    if instance and instance.status in TERMINAL_STATUSES:
                        return
                    await asyncio.sleep(1)

    return StreamingResponse(_generate(), media_type="text/event-stream")
```

## Template / Starter Code

```python
# app.py — FastAPI with lifespan, background loop, and port cleanup
import asyncio, os, signal, subprocess, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket

async def _poll_loop():
    while True:
        # Your reconciliation logic here
        await asyncio.sleep(2.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    poll_task = asyncio.create_task(_poll_loop())
    yield
    poll_task.cancel()

app = FastAPI(lifespan=lifespan)

def kill_stale_port_holder(port: int) -> None:
    try:
        result = subprocess.run(["lsof", "-ti", f":{port}"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            my_pid = os.getpid()
            for pid_str in result.stdout.strip().split("\n"):
                pid = int(pid_str.strip())
                if pid != my_pid:
                    os.kill(pid, signal.SIGTERM)
            time.sleep(1)
    except Exception:
        pass

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws")
async def ws_proxy(websocket: WebSocket):
    await websocket.accept()
    # ... bidirectional relay logic ...
```

## Gotchas & Lessons Learned

1. **The reconnect-counter bounce bug.** In one production system, the browser WebSocket was accepted immediately, then the proxy tried to connect to the backend. If the backend was dead, the WS closed. The browser's `onopen` had already fired (resetting reconnect attempts to 0), so the backoff never kicked in, causing rapid reconnect floods. Fix: verify the backend BEFORE calling `websocket.accept()`.

2. **`BaseHTTPMiddleware` doesn't cover WebSocket scope.** FastAPI's HTTP middleware is not invoked for WebSocket connections. Implement a separate auth check function for WebSocket endpoints.

3. **Self-signed TLS + WebSocket requires `verify=False`.** When your WebSocket proxy connects to an upstream service that uses self-signed TLS, the SSL context must explicitly trust self-signed certs or the websockets library will reject the connection.

4. **Orphan process cleanup on startup.** Kill orphaned child processes from a previous run during lifespan startup. Any service with child processes needs startup-time cleanup to avoid resource leaks.

5. **SSE file tailing needs a wait-for-file phase.** The events file may not exist when the SSE connection opens (the container is still starting). Poll for up to 60 seconds. Without this, the stream would immediately 404 during the startup window.
