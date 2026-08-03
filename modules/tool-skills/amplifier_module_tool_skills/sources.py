"""Skill source resolution for git URLs and remote sources.

Handles fetching skills from git repositories and caching them locally.
Uses amplifier-foundation's source resolver when available.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import signal
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Default cache directory for remote skills
DEFAULT_SKILLS_CACHE_DIR = Path("~/.amplifier/cache/skills").expanduser()

# Per-cache-path asyncio locks — defence-in-depth against concurrent clones.
# The primary guard is deduplication in resolve_skill_sources; the lock
# catches any residual concurrent access (e.g. direct calls to
# resolve_skill_source from outside resolve_skill_sources).
_clone_locks: dict[str, asyncio.Lock] = {}


def _get_clone_lock(cache_path: Path) -> asyncio.Lock:
    """Return the per-cache-path asyncio lock, creating it if needed."""
    key = str(cache_path)
    if key not in _clone_locks:
        _clone_locks[key] = asyncio.Lock()
    return _clone_locks[key]


def _parse_git_source(
    source: str, cache_dir: Path
) -> tuple[str, str, str | None, Path]:
    """Parse a git source URL into (url, ref, subdirectory, cache_path).

    Extracted from _resolve_remote_source so resolve_skill_sources can
    compute cache_paths upfront for deduplication without triggering I/O.

    The cache key is computed from url@ref ONLY (the #subdirectory= fragment
    is stripped), so all sources pointing at the same repo@ref share one
    cache_path regardless of how many different subdirectories they request.

    Returns:
        (bare_url, ref, subdirectory_or_None, cache_path)
    """
    url = source
    if url.startswith("git+"):
        url = url[4:]

    subdirectory = None
    if "#subdirectory=" in url:
        url, fragment = url.split("#", 1)
        if fragment.startswith("subdirectory="):
            subdirectory = fragment[13:]

    ref = "main"
    if "@" in url:
        url, ref = url.rsplit("@", 1)

    cache_key = hashlib.sha256(f"{url}@{ref}".encode()).hexdigest()[:16]
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
    cache_path = cache_dir / f"{repo_name}-{cache_key}"

    return url, ref, subdirectory, cache_path


def is_remote_source(source: str) -> bool:
    """Check if a source string is a secure remote URL (git+https://, https://).

    Only accepts encrypted transport protocols. http:// is intentionally
    rejected to prevent man-in-the-middle (MITM) attacks on skill sources.

    Args:
        source: Source string to check.

    Returns:
        True if source is a secure remote URL, False if local path or http://.
    """
    return source.startswith("git+") or source.startswith("https://")


async def resolve_skill_source(
    source: str, cache_dir: Path | None = None
) -> Path | None:
    """Resolve a skill source to a local directory path.

    Handles both local paths and remote URLs (git+https://).
    Remote sources are fetched and cached locally.

    Args:
        source: Source string - either a local path or git URL.
        cache_dir: Directory for caching remote skills.

    Returns:
        Path to local directory containing skills, or None if resolution fails.
    """
    cache_dir = cache_dir or DEFAULT_SKILLS_CACHE_DIR

    # Local path - just expand and return
    if not is_remote_source(source):
        path = Path(source).expanduser().resolve()
        if path.exists():
            return path
        logger.debug(f"Local skill source does not exist: {path}")
        return None

    # Remote source - use foundation's resolver
    try:
        return await _resolve_remote_source(source, cache_dir)
    except Exception as e:
        logger.warning(f"Failed to resolve remote skill source '{source}': {e}")
        return None


def _descendants(root: int) -> list[int]:
    """Every transitive child of `root`, read from /proc right now.

    Must be read BEFORE the direct child is reaped: once it is, the orphan is
    reparented to pid 1 and the ppid chain identifying it as ours is gone.
    """
    kids: dict[int, list[int]] = {}
    try:
        entries = os.listdir("/proc")
    except OSError:
        return []
    for name in entries:
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat", encoding="utf-8") as fh:
                ppid = int(fh.read().rsplit(")", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            continue
        kids.setdefault(ppid, []).append(int(name))
    out: list[int] = []
    stack = list(kids.get(root, []))
    while stack:
        pid = stack.pop()
        out.append(pid)
        stack.extend(kids.get(pid, []))
    return out


def _run_clone(cmd: list[str], env: dict[str, str], timeout: int):
    """`subprocess.run(capture_output=True, text=True, timeout=...)`, plus a
    TREE kill on timeout.

    CPython's `run()` kills only the DIRECT child when the timeout fires, so a
    `git-remote-http` that is blocked on `/dev/tty` outlives it as an orphan
    still holding the terminal. Defence in depth behind GIT_TERMINAL_PROMPT=0:
    if anything in the tree ever blocks on the terminal for another reason,
    the leak is still bounded by the timeout. The call remains SYNCHRONOUS --
    `Popen` + `communicate(timeout=...)` is exactly what `run()` does.
    """
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    ) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            tree = _descendants(proc.pid)  # BEFORE the kill
            proc.kill()
            for pid in tree:
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            proc.wait()
            raise
        return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)


async def _resolve_remote_source(source: str, cache_dir: Path) -> Path | None:
    """Resolve a remote source URL by cloning the git repository.

    Skills repos are simple collections of markdown files — they don't need
    pyproject.toml or bundle.md validation like Python packages do.

    The clone goes into a temporary directory and is renamed atomically into
    the final cache_path only after .amplifier_cache_meta.json is written.
    This ensures no sibling coroutine (or OS process) can ever observe a
    cache directory without metadata and mistake it for a corrupt clone.

    A per-cache-path asyncio lock serialises any concurrent callers within
    this process as defence-in-depth (the primary guard is deduplication in
    resolve_skill_sources).

    Args:
        source: Remote URL (git+https://, etc.).
        cache_dir: Directory for caching.

    Returns:
        Path to cached local directory, or None if resolution fails.
    """
    url, ref, subdirectory, cache_path = _parse_git_source(source, cache_dir)

    # Fast path: valid cache already present — no lock acquisition needed.
    if cache_path.exists():
        meta_file = cache_path / ".amplifier_cache_meta.json"
        if meta_file.exists():
            logger.debug(f"Using cached skill source: {cache_path}")
            result_path = cache_path / subdirectory if subdirectory else cache_path
            if result_path.exists():
                return result_path
            # Cache valid but requested subdirectory absent — fall through to
            # re-clone (subdirectory might have been added since last clone).

    # Slow path: acquire per-cache-path lock to serialise clones.
    cache_dir.mkdir(parents=True, exist_ok=True)
    async with _get_clone_lock(cache_path):
        # Re-check inside lock: another coroutine may have finished cloning
        # while we waited for the lock.
        if cache_path.exists():
            meta_file = cache_path / ".amplifier_cache_meta.json"
            if meta_file.exists():
                result_path = cache_path / subdirectory if subdirectory else cache_path
                return result_path if result_path.exists() else None
            else:
                # Stale directory without metadata (e.g. prior crash).
                # This path is unreachable in normal in-process use (the
                # deduplication in resolve_skill_sources prevents it), but
                # we still handle it for correctness.
                logger.warning(
                    f"Removing corrupt skills cache (no metadata): {cache_path}"
                )
                shutil.rmtree(cache_path)

        # Clone into a temp path so the final cache_path is never visible
        # without metadata (atomic publish on rename).
        tmp_path = cache_path.with_name(cache_path.name + ".tmp")
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)

        try:
            cmd = [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                ref,
                url,
                str(tmp_path),
            ]
            logger.info(f"Cloning skill source: {url}@{ref}")
            # A clone issued from inside the REPL must never PROMPT. When the
            # remote demands credentials, git opens /dev/tty BY PATH -- not the
            # inherited stdin -- and blocks reading it. The descriptor is held
            # by `git-remote-http`, which is NOT the process this timeout
            # kills: CPython kills only the direct child. The orphan survives,
            # keeps holding the terminal, and steals keystrokes from
            # prompt_toolkit's stdin reader -- the REPL freeze.
            # GIT_TERMINAL_PROMPT=0 makes git fail fast instead of prompting,
            # so nothing opens /dev/tty and nothing is orphaned. Credential
            # helpers, tokens embedded in the URL and GH_TOKEN-style auth are
            # unaffected: only INTERACTIVE prompting is disabled.
            env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            result = _run_clone(cmd, env=env, timeout=120)

            if result.returncode != 0:
                logger.error(f"Git clone failed: {result.stderr}")
                # Clean up partial clone
                if tmp_path.exists():
                    shutil.rmtree(tmp_path, ignore_errors=True)
                return None

            # Write cache metadata to the temp dir (still not visible at cache_path)
            _sha_result = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "HEAD",
                cwd=str(tmp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _sha_stdout, _ = await _sha_result.communicate()
            _commit_sha = (
                _sha_stdout.decode().strip() if _sha_result.returncode == 0 else ""
            )
            _meta = {
                "cached_at": datetime.now().isoformat(),
                "ref": ref,
                "commit": _commit_sha,
                "git_url": url,
                "type": "skills",
            }
            (tmp_path / ".amplifier_cache_meta.json").write_text(
                json.dumps(_meta, indent=2), encoding="utf-8"
            )

            # Atomically publish: rename temp dir to final cache_path.
            # If cache_path now exists (cross-process race; another OS process
            # beat us), discard our temp clone and use theirs.
            if cache_path.exists():
                shutil.rmtree(tmp_path, ignore_errors=True)
            else:
                tmp_path.rename(cache_path)

            result_path = cache_path / subdirectory if subdirectory else cache_path
            if result_path.exists():
                logger.info(f"Resolved remote skill source: {source} -> {result_path}")
                return result_path
            else:
                logger.warning(f"Subdirectory not found in cloned repo: {subdirectory}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"Git clone timed out for: {url}")
            if tmp_path.exists():
                shutil.rmtree(tmp_path, ignore_errors=True)
            return None
        except Exception as e:
            logger.error(f"Failed to clone skill source '{source}': {e}")
            if tmp_path.exists():
                shutil.rmtree(tmp_path, ignore_errors=True)
            return None


async def resolve_skill_sources(
    sources: list[str], cache_dir: Path | None = None
) -> list[Path]:
    """Resolve multiple skill sources to local directory paths.

    Processes sources in order, preserving priority (first source = highest priority).

    Remote sources that share the same url@ref (and therefore the same cache_path)
    are deduplicated BEFORE the concurrent gather: exactly one clone task fires per
    unique cache_path.  Without this, N concurrent tasks would all observe an
    in-progress clone as "directory exists but no metadata", log the destructive
    "Removing corrupt skills cache" warning, rmtree the live clone, and re-clone —
    resulting in N clones and N-1 spurious warnings.

    Args:
        sources: List of source strings (local paths or git URLs).
        cache_dir: Directory for caching remote skills.

    Returns:
        List of resolved local paths (in priority order).
    """
    cache_dir = cache_dir or DEFAULT_SKILLS_CACHE_DIR

    # Separate local and remote sources while preserving order info
    local_sources: list[tuple[int, str]] = []
    remote_sources: list[tuple[int, str]] = []

    for i, source in enumerate(sources):
        if is_remote_source(source):
            remote_sources.append((i, source))
        else:
            local_sources.append((i, source))

    # Resolve local sources immediately (no I/O needed)
    results: dict[int, Path | None] = {}
    for i, source in local_sources:
        path = Path(source).expanduser().resolve()
        if path.exists():
            results[i] = path
        else:
            logger.debug(f"Local skill source does not exist: {path}")
            results[i] = None

    if remote_sources:
        # Deduplicate by cache_path: sources sharing the same url@ref map to the
        # same cache directory and must not be cloned concurrently.
        # The first occurrence of each cache_path triggers the clone;
        # subsequent occurrences resolve after the clone completes (cache hit).
        seen_cache_paths: set[Path] = set()
        unique_remote: list[tuple[int, str]] = []  # one representative per cache_path
        dup_remote: list[tuple[int, str]] = []  # all others — will hit cache

        for i, source in remote_sources:
            _, _, _, cache_path = _parse_git_source(source, cache_dir)
            if cache_path not in seen_cache_paths:
                seen_cache_paths.add(cache_path)
                unique_remote.append((i, source))
            else:
                dup_remote.append((i, source))

        async def resolve_with_index(i: int, source: str) -> tuple[int, Path | None]:
            path = await resolve_skill_source(source, cache_dir)
            return (i, path)

        # Phase 1: clone unique repos concurrently.
        # No two tasks in this gather share a cache_path, so there is no race.
        unique_results = await asyncio.gather(
            *[resolve_with_index(i, s) for i, s in unique_remote]
        )
        for i, path in unique_results:
            results[i] = path

        # Phase 2: resolve duplicate sources — all hit the now-populated cache.
        if dup_remote:
            dup_results = await asyncio.gather(
                *[resolve_with_index(i, s) for i, s in dup_remote]
            )
            for i, path in dup_results:
                results[i] = path

    # Reconstruct ordered list, filtering out None values
    resolved_paths: list[Path] = []
    for i in sorted(results.keys()):
        path = results[i]
        if path is not None:
            resolved_paths.append(path)

    logger.info(
        f"Resolved {len(resolved_paths)} skill sources from {len(sources)} configured"
    )
    return resolved_paths
