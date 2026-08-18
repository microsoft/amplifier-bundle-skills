"""Tests for sources.py - cache metadata written after git clone."""

import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from amplifier_module_tool_skills.sources import _resolve_remote_source

# These tests intercept the clone at the module's own boundary, _run_clone,
# rather than at subprocess.run/Popen. _run_clone is what _resolve_remote_source
# actually calls, so the seam stays valid even if the helper's internals change
# (it uses Popen + communicate to allow a process-TREE kill on timeout; mocking
# Popen here would couple these tests to CPython plumbing).
_CLONE_SEAM = "amplifier_module_tool_skills.sources._run_clone"


def _compute_cache_path(source: str, cache_dir: Path) -> Path:
    """Compute the expected cache directory path for a given source URL.

    Mirrors the cache-key logic in _resolve_remote_source so tests can
    pre-create (or inspect) the right directory without calling the real function.
    """
    url = source
    if url.startswith("git+"):
        url = url[4:]
    if "#subdirectory=" in url:
        url, _ = url.split("#", 1)
    ref = "main"
    if "@" in url:
        url, ref = url.rsplit("@", 1)
    cache_key = hashlib.sha256(f"{url}@{ref}".encode()).hexdigest()[:16]
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
    return cache_dir / f"{repo_name}-{cache_key}"


@pytest.mark.asyncio
async def test_write_cache_meta_after_successful_clone(tmp_path):
    """After a successful git clone, .amplifier_cache_meta.json is written."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    source = "git+https://github.com/example/my-skills@main"

    def fake_clone(cmd, **kwargs):
        """Simulate git clone by creating the destination directory."""
        if "clone" in cmd:
            dest = Path(cmd[-1])
            dest.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    mock_sha_proc = AsyncMock()
    mock_sha_proc.returncode = 0
    mock_sha_proc.communicate = AsyncMock(return_value=(b"abc1234deadbeef\n", b""))

    with patch(_CLONE_SEAM, side_effect=fake_clone):
        with patch("asyncio.create_subprocess_exec", return_value=mock_sha_proc):
            result = await _resolve_remote_source(source, cache_dir)

    assert result is not None, "Expected a resolved path"

    meta_files = list(cache_dir.glob("*/.amplifier_cache_meta.json"))
    assert len(meta_files) == 1, (
        "Expected exactly one .amplifier_cache_meta.json in the cache directory"
    )

    meta = json.loads(meta_files[0].read_text())
    assert meta["git_url"] == "https://github.com/example/my-skills"
    assert meta["ref"] == "main"
    assert meta["type"] == "skills"
    assert meta["commit"] == "abc1234deadbeef"
    assert "cached_at" in meta


@pytest.mark.asyncio
async def test_corrupt_cache_without_metadata_triggers_reclone(tmp_path):
    """A directory without .amplifier_cache_meta.json is treated as corrupt and re-cloned.

    Reproduces: git clone leaves a partial directory when it fails mid-download.
    The next session must detect the corrupt state and re-clone, not return the
    partial directory as a valid cache.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    source = "git+https://github.com/example/my-skills@main"

    # Pre-create a directory that looks like a partial clone: exists but no metadata
    corrupt_cache = _compute_cache_path(source, cache_dir)
    corrupt_cache.mkdir(parents=True)
    # No .amplifier_cache_meta.json written -- simulates a mid-download failure

    clone_called = []

    def fake_clone(cmd, **kwargs):
        """Simulate a successful git clone (re-clone after detecting corruption)."""
        if "clone" in cmd:
            clone_called.append(cmd)
            dest = Path(cmd[-1])
            dest.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    mock_sha_proc = AsyncMock()
    mock_sha_proc.returncode = 0
    mock_sha_proc.communicate = AsyncMock(return_value=(b"deadbeef12345678\n", b""))

    with patch(_CLONE_SEAM, side_effect=fake_clone):
        with patch("asyncio.create_subprocess_exec", return_value=mock_sha_proc):
            result = await _resolve_remote_source(source, cache_dir)

    assert result is not None, "Expected a resolved path after re-clone"
    assert len(clone_called) == 1, (
        "Expected exactly one git clone call (corrupt cache should trigger re-clone, "
        "not an early return)"
    )

    meta_files = list(cache_dir.glob("*/.amplifier_cache_meta.json"))
    assert len(meta_files) == 1, "Expected metadata written after successful re-clone"


@pytest.mark.asyncio
async def test_failed_clone_cleans_up_partial_directory(tmp_path):
    """When a git clone fails, the partial directory is cleaned up.

    Reproduces: a failed clone leaves a partial .git directory behind, causing
    subsequent attempts to fail with 'shallow.lock: File exists'.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    source = "git+https://github.com/example/my-skills@main"

    expected_cache = _compute_cache_path(source, cache_dir)

    def fake_failing_clone(cmd, **kwargs):
        """Simulate a git clone that fails mid-download (creates a partial directory)."""
        stderr = (
            "error: unable to write file .git/objects/pack/pack-abc.pack: "
            "No such file or directory\nfatal: unable to rename temporary '*.pack' file"
        )
        # Simulate the partial directory left behind by a failed clone
        if "clone" in cmd:
            dest = Path(cmd[-1])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / ".git").mkdir()  # partial .git directory
        return subprocess.CompletedProcess(cmd, 128, "", stderr)  # 128 = git failure

    with patch(_CLONE_SEAM, side_effect=fake_failing_clone):
        result = await _resolve_remote_source(source, cache_dir)

    assert result is None, "Expected None when clone fails"
    assert not expected_cache.exists(), (
        "Partial directory should be cleaned up after a failed clone to prevent "
        "stale lock files on the next attempt"
    )


@pytest.mark.asyncio
async def test_leftover_readonly_tmp_is_healed_before_reclone(tmp_path):
    """A prior failed clone can leave a read-only ``.tmp`` staging dir behind.

    Reproduces the Windows-permanent-failure bug: git marks pack files
    (``.git/objects/pack/*.idx``) read-only. On Windows the read-only
    attribute lives on the file and blocks deletion, so the old
    ``shutil.rmtree(tmp_path, ignore_errors=True)`` at the pre-clone cleanup
    silently no-ops, the ``.tmp`` survives, and every subsequent clone dies
    with 'destination path already exists and is not an empty directory' --
    forever. ``rmtree_robust`` must clear the read-only bit and remove it so
    the re-clone proceeds.

    On POSIX a read-only file is removable when its parent dir is writable, so
    this test passes trivially on Linux/macOS. It genuinely fails pre-fix and
    passes post-fix on Windows; keeping it cross-platform documents the
    contract and guards it once a Windows CI leg exists.
    """
    import os
    import stat

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    source = "git+https://github.com/example/my-skills@main"

    expected_cache = _compute_cache_path(source, cache_dir)
    # Pre-seed the orphaned .tmp a prior failed clone would have left behind,
    # with a read-only pack file inside it (the exact thing that jams Windows).
    tmp_leftover = expected_cache.with_name(expected_cache.name + ".tmp")
    pack_dir = tmp_leftover / ".git" / "objects" / "pack"
    pack_dir.mkdir(parents=True)
    stuck = pack_dir / "pack-abc.idx"
    stuck.write_text("readonly pack index", encoding="utf-8")
    os.chmod(stuck, stat.S_IREAD)  # 0o444 — read-only, as git leaves it

    def fake_clone(cmd, **kwargs):
        """A now-successful clone into the (freshly cleared) tmp dir."""
        if "clone" in cmd:
            dest = Path(cmd[-1])
            # git refuses a non-empty destination; if the leftover wasn't
            # cleared this returns 128 and the test's assertions below fail.
            if dest.exists() and any(dest.iterdir()):
                return subprocess.CompletedProcess(
                    cmd,
                    128,
                    "",
                    f"fatal: destination path '{dest}' already exists and is "
                    "not an empty directory.",
                )
            dest.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    mock_sha_proc = AsyncMock()
    mock_sha_proc.returncode = 0
    mock_sha_proc.communicate = AsyncMock(return_value=(b"feedface00000000\n", b""))

    try:
        with patch(_CLONE_SEAM, side_effect=fake_clone):
            with patch("asyncio.create_subprocess_exec", return_value=mock_sha_proc):
                result = await _resolve_remote_source(source, cache_dir)
    finally:
        # Never leave a read-only file that would jam pytest's own tmp cleanup.
        if stuck.exists():
            os.chmod(stuck, stat.S_IWRITE | stat.S_IREAD)

    assert not tmp_leftover.exists(), (
        "The orphaned read-only .tmp staging dir must be cleared before the "
        "re-clone; if it survives, git aborts on a non-empty destination and "
        "the source can never resolve again."
    )
    assert result is not None, "Expected a resolved path after the leftover was healed"


@pytest.mark.asyncio
async def test_valid_cache_with_metadata_returned_without_reclone(tmp_path):
    """A cache directory with .amplifier_cache_meta.json is returned directly.

    Verifies the happy path: a valid cache (metadata present = successful prior clone)
    must be returned without invoking git at all.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    source = "git+https://github.com/example/my-skills@main"

    # Pre-create a valid-looking cache with metadata
    valid_cache = _compute_cache_path(source, cache_dir)
    valid_cache.mkdir(parents=True)
    (valid_cache / ".amplifier_cache_meta.json").write_text(
        json.dumps(
            {
                "cached_at": "2026-01-01T00:00:00",
                "ref": "main",
                "commit": "cafecafe12345678",
                "git_url": "https://github.com/example/my-skills",
                "type": "skills",
            }
        ),
        encoding="utf-8",
    )

    with patch(_CLONE_SEAM) as mock_clone:
        result = await _resolve_remote_source(source, cache_dir)

    assert result == valid_cache, "Expected the pre-existing valid cache path"
    mock_clone.assert_not_called()  # no git clone should happen for a valid cache
