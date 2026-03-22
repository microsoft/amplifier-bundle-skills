"""Skill source resolution for git URLs and remote sources.

Handles fetching skills from git repositories and caching them locally.
Uses amplifier-foundation's source resolver when available.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Default cache directory for remote skills
DEFAULT_SKILLS_CACHE_DIR = Path("~/.amplifier/cache/skills").expanduser()


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


async def _resolve_remote_source(source: str, cache_dir: Path) -> Path | None:
    """Resolve a remote source URL by cloning the git repository.

    Skills repos are simple collections of markdown files - they don't need
    pyproject.toml or bundle.md validation like Python packages do.

    Args:
        source: Remote URL (git+https://, etc.).
        cache_dir: Directory for caching.

    Returns:
        Path to cached local directory, or None if resolution fails.
    """
    # Parse the git URL
    # Format: git+https://github.com/org/repo@branch
    # or: git+https://github.com/org/repo@branch#subdirectory=path
    url = source
    if url.startswith("git+"):
        url = url[4:]

    # Extract subdirectory if specified
    subdirectory = None
    if "#subdirectory=" in url:
        url, fragment = url.split("#", 1)
        if fragment.startswith("subdirectory="):
            subdirectory = fragment[13:]

    # Extract branch/ref if specified
    ref = "main"  # default
    if "@" in url:
        url, ref = url.rsplit("@", 1)

    # Create cache key from URL
    cache_key = hashlib.sha256(f"{url}@{ref}".encode()).hexdigest()[:16]
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
    cache_path = cache_dir / f"{repo_name}-{cache_key}"

    # Check if already cached (valid = has metadata written after successful clone)
    if cache_path.exists():
        meta_file = cache_path / ".amplifier_cache_meta.json"
        if meta_file.exists():
            logger.debug(f"Using cached skill source: {cache_path}")
            result_path = cache_path / subdirectory if subdirectory else cache_path
            if result_path.exists():
                return result_path
            # Cache valid but subdirectory doesn't exist - fall through to re-clone
        else:
            # Directory exists but no metadata = corrupt/partial clone
            logger.warning(f"Removing corrupt skills cache (no metadata): {cache_path}")
        # Fall through to cleanup and re-clone

    # Clone the repository
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Remove stale cache if exists
        if cache_path.exists():
            shutil.rmtree(cache_path)

        # Clone with depth=1 for efficiency
        cmd = ["git", "clone", "--depth", "1", "--branch", ref, url, str(cache_path)]
        logger.info(f"Cloning skill source: {url}@{ref}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            logger.error(f"Git clone failed: {result.stderr}")
            # Clean up partial clone to prevent stale lock files on next attempt
            if cache_path.exists():
                shutil.rmtree(cache_path, ignore_errors=True)
            return None

        # Write cache metadata so `amplifier update` can track and refresh this cache
        _sha_result = await asyncio.create_subprocess_exec(
            "git",
            "rev-parse",
            "HEAD",
            cwd=str(cache_path),
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
        (cache_path / ".amplifier_cache_meta.json").write_text(
            json.dumps(_meta, indent=2), encoding="utf-8"
        )

        result_path = cache_path / subdirectory if subdirectory else cache_path
        if result_path.exists():
            logger.info(f"Resolved remote skill source: {source} -> {result_path}")
            return result_path
        else:
            logger.warning(f"Subdirectory not found in cloned repo: {subdirectory}")
            return None

    except subprocess.TimeoutExpired:
        logger.error(f"Git clone timed out for: {url}")
        if cache_path.exists():
            shutil.rmtree(cache_path, ignore_errors=True)
        return None
    except Exception as e:
        logger.error(f"Failed to clone skill source '{source}': {e}")
        if cache_path.exists():
            shutil.rmtree(cache_path, ignore_errors=True)
        return None


async def resolve_skill_sources(
    sources: list[str], cache_dir: Path | None = None
) -> list[Path]:
    """Resolve multiple skill sources to local directory paths.

    Processes sources in order, preserving priority (first source = highest priority).
    Remote sources are fetched in parallel for efficiency.

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

    # Resolve remote sources in parallel
    if remote_sources:

        async def resolve_with_index(i: int, source: str) -> tuple[int, Path | None]:
            path = await resolve_skill_source(source, cache_dir)
            return (i, path)

        tasks = [resolve_with_index(i, source) for i, source in remote_sources]
        remote_results = await asyncio.gather(*tasks)

        for i, path in remote_results:
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
