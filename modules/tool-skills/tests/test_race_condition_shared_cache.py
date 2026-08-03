"""Tests for the race condition where N sources sharing one url@ref triggered N clones.

Reproduces and verifies the fix for resolve_skill_sources firing concurrent
asyncio.gather tasks on the same cache_path when multiple sources share the
same git repo@ref (differ only by #subdirectory=).

The race in the old code (reproduced by this test):
- The skills cache is empty (e.g. right after `amplifier reset`).
- 5 sources share the same url@ref, differing only by their #subdirectory= fragment.
- resolve_skill_sources fires all 5 via asyncio.gather.
- Task 0: clones (synchronous subprocess.run), then hits
    `await asyncio.create_subprocess_exec(...)`, yielding to the event loop
    BEFORE metadata is written.
- Tasks 1-4: each wakes up, sees "directory exists but no metadata", emits
    "Removing corrupt skills cache (no metadata)", shutil.rmtrees the live
    clone, and re-clones. Result: 5 clones, 4 spurious destructive warnings.

The fix: deduplicate by cache_path BEFORE the concurrent gather so only one
clone task fires per unique repo@ref.
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amplifier_module_tool_skills.sources import resolve_skill_sources

# Intercept the clone at the module's own boundary, _run_clone, rather than at
# subprocess.run/Popen -- see the note in test_sources.py.
_CLONE_SEAM = "amplifier_module_tool_skills.sources._run_clone"


# The 5 context-intelligence bundle sources that originally triggered the bug.
BASE_URL = "git+https://github.com/microsoft/amplifier-bundle-context-intelligence@main"
SUBDIRS = [
    "skills/blob-reading",
    "skills/context-intelligence-graph-query",
    "skills/context-intelligence-session-navigation",
    "skills/context-intelligence-session-reconstruction",
    "skills/workflow-pattern-analysis",
]


@pytest.mark.asyncio
async def test_shared_repo_ref_cloned_exactly_once(tmp_path, caplog):
    """5 sources sharing one repo@ref trigger exactly one git clone, not five.

    Concurrency is exercised by making the fake asyncio.create_subprocess_exec
    call ``await asyncio.sleep(0)``, which explicitly yields to the event loop at
    the same point the real coroutine would — after the synchronous git clone
    completes but before metadata is written.  In the old code:
      - Task 0 clones, yields at the sleep(0)
      - Tasks 1-4 each find "directory exists, no metadata" => corrupt warning =>
        rmtree => re-clone => yield
    Result: clone_call_count == 5, 4 warnings.

    After the fix, clone_call_count == 1 and no warnings.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    sources = [f"{BASE_URL}#subdirectory={sd}" for sd in SUBDIRS]
    clone_call_count = 0

    def fake_run_clone(cmd, **kwargs):
        nonlocal clone_call_count
        if "clone" in cmd:
            clone_call_count += 1
            dest = Path(cmd[-1])
            dest.mkdir(parents=True, exist_ok=True)
            # Populate every expected subdirectory so each source can resolve.
            for sd in SUBDIRS:
                (dest / sd).mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    async def fake_create_subprocess_exec(*args, **kwargs):
        # Yield to the event loop — the critical interleaving point.
        # In the broken code Task 0 clones (sync), hits this await, yields;
        # Tasks 1-4 run and see "cache dir exists, no metadata" => race fires.
        await asyncio.sleep(0)
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"abc1234deadbeef\n", b""))
        return mock_proc

    with caplog.at_level(
        logging.WARNING, logger="amplifier_module_tool_skills.sources"
    ):
        with patch(_CLONE_SEAM, side_effect=fake_run_clone):
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                result_paths = await resolve_skill_sources(sources, cache_dir)

    # PRIMARY: exactly ONE git clone for the shared repo@ref.
    assert clone_call_count == 1, (
        f"Expected exactly 1 clone for the shared repo@ref, got {clone_call_count}. "
        "Race condition: concurrent tasks each cloned the same cache_path."
    )

    # All 5 sources resolve to their distinct, correct subdirectory paths.
    assert len(result_paths) == 5, (
        f"Expected 5 resolved paths (one per subdirectory), got {len(result_paths)}"
    )
    for i, sd in enumerate(SUBDIRS):
        expected_tail = Path(sd).parts
        actual_tail = result_paths[i].parts[-len(expected_tail) :]
        assert actual_tail == expected_tail, (
            f"Source {i} ({sd!r}) should resolve to a path ending in {sd!r}, "
            f"got: {result_paths[i]}"
        )

    # No spurious "Removing corrupt skills cache" warnings.
    corrupt_warnings = [
        r.message
        for r in caplog.records
        if "Removing corrupt skills cache" in r.message
    ]
    assert corrupt_warnings == [], (
        f"Unexpected 'Removing corrupt skills cache' warnings: {corrupt_warnings}. "
        "Race condition: a sibling task destructively rmtree'd an in-progress clone."
    )
