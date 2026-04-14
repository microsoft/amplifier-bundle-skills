---
name: container-orchestration-patterns
description: >
  Use when running tasks in Docker containers with safety limits, watchdog
  monitoring for resource enforcement, orphan container recovery, sidecar
  container provisioning, or scripting reproducible dev stack environments.
---

# Container Orchestration & Dev Stacks

## The Pattern

**Problem:** You're executing tasks in containers (one per task). Those tasks can fork-bomb, exhaust memory, run forever, or leave orphan containers after a crash. You need safety limits, monitoring, and cleanup — plus optional sidecar services (databases, caches, auxiliary APIs).

**Approach:** Hard container limits (PID, memory, CPU, lifetime), a watchdog loop that polls `docker stats` and kills violators, orphan recovery on restart, and sidecar provisioning with bind-mounted persistent data.

Pattern proven in production across multiple Python CLI tools and web services.

## Key Design Decisions

### 1. Container safety limits — the runaway processes incident

Safety limits exist because of a real incident: in one production deployment, over 4,000 runaway test processes consumed 103Gi of RAM and caused OOM kills across the host.

```python
# Container safety limits — prevent fork bomb and memory exhaustion incidents.
# These values were determined after a real incident where thousands of runaway
# processes consumed all available RAM and caused OOM kills.
CONTAINER_PIDS_LIMIT = 256
CONTAINER_MEMORY_LIMIT = "8g"
CONTAINER_MEMORY_SWAP_LIMIT = "8g"
CONTAINER_CPU_LIMIT = 2.0
MAX_INSTANCE_LIFETIME_SECONDS = 12 * 60 * 60  # 12 hours
```

These are passed to `docker create` as resource constraints. The PID limit is the most critical — it prevents fork bombs from escaping the container's cgroup.

### 2. Watchdog monitoring loop

The watchdog runs as a background `asyncio` task, polling every 5 minutes:

```python
async def watchdog_loop(self, instance_store, interval=300):
    while True:
        for instance_id, info in list(self._active.items()):
            await self._watchdog_check_instance(instance_id, info, instance_store)
        await asyncio.sleep(interval)

async def _watchdog_check_instance(self, instance_id, info, instance_store):
    container_name = info.container_name

    # Check 1: Lifetime
    if age_seconds > MAX_INSTANCE_LIFETIME_SECONDS:
        await self._watchdog_destroy(instance_id, ...)
        return

    # Check 2 & 3: PIDs and Memory (single docker stats call)
    rc, stdout, _ = await self._client._run_docker(
        "stats", "--no-stream", "--format", "{{.PIDs}} {{.MemPerc}}",
        container_name)
    parts = stdout.strip().split()
    pid_count = int(parts[0])
    mem_perc = float(parts[1].rstrip("%"))

    if pid_count > _WATCHDOG_PID_THRESHOLD:     # 200
        await self._watchdog_destroy(...)
        return
    if mem_perc > _WATCHDOG_MEMORY_PERCENT_THRESHOLD:  # 80%
        await self._watchdog_destroy(...)
        return
```

Key design: the watchdog uses `docker stats --no-stream` with a format string to get both PID count and memory percentage in a single call. This minimizes Docker API overhead.

The thresholds (`_WATCHDOG_PID_THRESHOLD = 200`, `_WATCHDOG_MEMORY_PERCENT_THRESHOLD = 80.0`) are below the hard limits (`CONTAINER_PIDS_LIMIT = 256`, `CONTAINER_MEMORY_LIMIT = "8g"`). This gives the watchdog a chance to detect and kill containers before they hit the hard limit and get OOM-killed by the kernel.

### 3. Watchdog destroy — cleanup with sidecar awareness

Destroying a container also destroys its sidecar containers:

```python
async def _watchdog_destroy(self, instance_id, container_name, instance_store):
    # Destroy the main container
    await self._client.destroy_container(container_name)
    # Destroy sidecar if present
    info = self._active.get(instance_id)
    if info is not None and info.sidecar_env_id is not None:  # Destroy companion containers if your architecture uses them
        await destroy_sidecar(info.sidecar_env_id)
    # Update status and remove from active tracking
    instance_store.update_instance(instance_id, status="cancelled")
    self._active.pop(instance_id, None)
```

### 4. Orphan container recovery on service restart

When the orchestrator starts, it checks for containers that were active before the crash/restart. The lifespan preserves active instances across upgrades:

```python
old_orchestrator = app.state.orchestrator
new_orchestrator = Orchestrator(client=client)
if old_orchestrator and hasattr(old_orchestrator, "_active"):
    new_orchestrator._active.update(old_orchestrator._active)
    logger.info("Preserved %d active instances during orchestrator upgrade",
                len(old_orchestrator._active))
```

### 5. Sidecar provisioning — persistent data via bind mounts

Each task instance can get a dedicated sidecar container (e.g., a database, cache, or auxiliary API):

```python
async def create_sidecar_for_instance(instance_id: str) -> SidecarInfo | None:
    """Create a sidecar with data bind-mounted to the instance directory."""
    host_data_path = get_instance_dir(instance_id) / SIDECAR_DATA_DIR
    host_data_path.mkdir(parents=True, exist_ok=True)
    return await asyncio.to_thread(_create_sidecar_sync, docker_network,
                                    str(host_data_path))
```

The bind mount at `/data` means sidecar data (repos, databases) survives container destruction — it persists in the instance directory.

Network-aware URLs handle the container-vs-host split:

```python
url = "http://sidecar:3000" if docker_network else f"http://host.docker.internal:{port}"
```

When containers share a Docker network, they reach the sidecar via DNS name. When not on a shared network (dev mode), they use `host.docker.internal` to reach the host-mapped port.

## Template / Starter Code

```python
# orchestrator.py — container lifecycle with safety limits and watchdog
import asyncio, time, logging, subprocess

PIDS_LIMIT = 256
MEMORY_LIMIT = "8g"
CPU_LIMIT = 2.0
MAX_LIFETIME = 12 * 60 * 60  # 12 hours
WATCHDOG_PID_THRESHOLD = 200
WATCHDOG_MEM_THRESHOLD = 80.0

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        self._active: dict[str, dict] = {}  # instance_id → {container, started_at}

    async def start_instance(self, instance_id: str, image: str, cmd: list[str]):
        container_name = f"inst-{instance_id[:12]}"
        proc = await asyncio.create_subprocess_exec(
            "docker", "create",
            "--name", container_name,
            "--pids-limit", str(PIDS_LIMIT),
            "--memory", MEMORY_LIMIT,
            "--cpus", str(CPU_LIMIT),
            image, *cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        await asyncio.create_subprocess_exec("docker", "start", container_name)
        self._active[instance_id] = {
            "container": container_name,
            "started_at": time.time(),
        }

    async def watchdog_loop(self, interval: float = 300):
        while True:
            for iid, info in list(self._active.items()):
                await self._check(iid, info)
            await asyncio.sleep(interval)

    async def _check(self, instance_id: str, info: dict):
        container = info["container"]
        age = time.time() - info["started_at"]
        if age > MAX_LIFETIME:
            logger.warning("Lifetime exceeded for %s", instance_id)
            await self._destroy(instance_id, container)
            return
        proc = await asyncio.create_subprocess_exec(
            "docker", "stats", "--no-stream", "--format", "{{.PIDs}} {{.MemPerc}}",
            container, stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        parts = stdout.decode().strip().split()
        if len(parts) >= 2:
            pids = int(parts[0])
            mem = float(parts[1].rstrip("%"))
            if pids > WATCHDOG_PID_THRESHOLD or mem > WATCHDOG_MEM_THRESHOLD:
                logger.warning("Resource violation: %s (pids=%d, mem=%.1f%%)",
                               instance_id, pids, mem)
                await self._destroy(instance_id, container)

    async def _destroy(self, instance_id: str, container: str):
        proc = await asyncio.create_subprocess_exec(
            "docker", "rm", "-f", container)
        await proc.communicate()
        self._active.pop(instance_id, None)
```

## Gotchas & Lessons Learned

1. **The runaway processes incident.** Before PID limits existed, an automated agent ran a test suite in a loop. Each test process forked subprocesses. The container had no `--pids-limit`, so the cascade consumed over 100Gi of RAM and OOM-killed other workloads on the host. The fix was twofold: hard Docker `--pids-limit=256` AND a software process guard that kills orphan test patterns between commands.

2. **Watchdog thresholds must be below hard limits.** The watchdog threshold for PIDs (200) is below the Docker limit (256). If the watchdog only fired at 256, the container might already be stuck in a fork bomb where new processes can't spawn but existing ones consume resources. The gap gives the watchdog a window to act.

3. **`docker stats --no-stream` is the cheapest monitoring.** A single `docker stats` call returns PIDs and memory in one shot. The format string `{{.PIDs}} {{.MemPerc}}` extracts just what we need. Alternative approaches (reading cgroup files, Docker API) are more complex for no benefit.

4. **Sidecar data must be bind-mounted for persistence.** Without the bind mount, destroying the sidecar container destroys all data created during the instance's run. The bind mount to the instance directory means data survives even after the sidecar is cleaned up.

5. **The `host.docker.internal` vs Docker network split.** In dev mode (no shared Docker network), containers reach host services via `host.docker.internal`. In production (shared network), they use container DNS names. Your service abstraction should handle this with separate `host` and `container_host` fields.
