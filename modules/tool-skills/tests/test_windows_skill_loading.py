"""Windows-compatibility tests for the tool-skills load/discovery path.

Three bugs were fixed:
  1. SKILL.md was read as "utf-8" (not "utf-8-sig"). A Windows-authored file
     (Notepad, PowerShell Out-File, many editors) is UTF-8 WITH a BOM, so the
     retained \ufeff made content.startswith("---") False and the skill was
     silently dropped ("missing YAML frontmatter"). TEETH ON LINUX -- the BOM
     behaviour is platform-independent, so the old code fails this test here too.
  2. The shell-command timeout handler called os.killpg/os.getpgid/SIGKILL,
     which do not exist on Windows -> AttributeError + orphaned child. Verified
     BEHAVIOURALLY: the timeout branch is driven with os.name forced to "nt" and
     the kill calls are observed, so the test fails if the guard is removed,
     misplaced, or refactored into a no-op.
  3. _build_safe_env()'s allowlist was POSIX-only vocabulary, so cmd.exe (which
     create_subprocess_shell uses on Windows) lost SystemRoot/ComSpec/PATHEXT
     and failed to spawn. Verified by asserting the Windows allowlist carries
     those keys and matches case-insensitively.
"""

import os
import signal
from pathlib import Path
from unittest.mock import patch

from amplifier_module_tool_skills.discovery import extract_skill_body
from amplifier_module_tool_skills.discovery import parse_skill_frontmatter

# NB: the _SAFE_ENV_KEYS_WINDOWS / _build_safe_env imports are done lazily inside
# the env tests below, NOT at module scope. Otherwise, running this file against
# the UN-fixed code (where those symbols don't exist) would fail at COLLECTION and
# mask the BOM teeth -- the BOM tests only need discovery, which exists on baseline.

_SKILL = "---\nname: bom-skill\ndescription: A skill\nversion: 1.0.0\n---\nBody here\n"


class TestBomFrontmatter:
    """Bug 1: a UTF-8 BOM must not hide the frontmatter. Teeth on Linux."""

    def test_frontmatter_parsed_from_bom_file(self, tmp_path: Path):
        f = tmp_path / "SKILL.md"
        # Write UTF-8 WITH BOM, exactly as a Windows editor would.
        f.write_bytes(b"\xef\xbb\xbf" + _SKILL.encode("utf-8"))
        fm = parse_skill_frontmatter(f)
        assert fm is not None, "BOM'd SKILL.md was dropped as if it had no frontmatter"
        assert fm["name"] == "bom-skill"

    def test_body_extracted_from_bom_file(self, tmp_path: Path):
        f = tmp_path / "SKILL.md"
        f.write_bytes(b"\xef\xbb\xbf" + _SKILL.encode("utf-8"))
        body = extract_skill_body(f)
        assert body == "Body here"

    def test_plain_utf8_still_parses(self, tmp_path: Path):
        # No regression: a normal (no-BOM) file still works.
        f = tmp_path / "SKILL.md"
        f.write_text(_SKILL, encoding="utf-8")
        fm = parse_skill_frontmatter(f)
        assert fm is not None and fm["name"] == "bom-skill"

    def test_crlf_bom_file_parses(self, tmp_path: Path):
        # The nastiest real Windows file: BOM + CRLF line endings.
        f = tmp_path / "SKILL.md"
        f.write_bytes(b"\xef\xbb\xbf" + _SKILL.replace("\n", "\r\n").encode("utf-8"))
        fm = parse_skill_frontmatter(f)
        assert fm is not None and fm["name"] == "bom-skill"


class TestWindowsSafeEnv:
    """Bug 3: the shell-exec env allowlist must be Windows-viable."""

    def test_windows_allowlist_has_cmd_essentials(self):
        # Lazy import (see module docstring) so this file collects against the
        # un-fixed code where these symbols don't yet exist.
        from amplifier_module_tool_skills.preprocessing import _SAFE_ENV_KEYS_WINDOWS

        upper = {k.upper() for k in _SAFE_ENV_KEYS_WINDOWS}
        for essential in ("SYSTEMROOT", "COMSPEC", "PATHEXT", "PATH", "TEMP"):
            assert essential in upper, (
                f"{essential} missing from Windows safe-env allowlist"
            )

    def test_build_safe_env_forwards_systemroot_on_windows(self):
        from amplifier_module_tool_skills.preprocessing import _build_safe_env

        fake_env = {
            "SystemRoot": r"C:\Windows",  # note the real-world mixed case
            "ComSpec": r"C:\Windows\System32\cmd.exe",
            "PATH": r"C:\Windows",
            "SECRET_API_KEY": "sk-must-not-leak",
        }
        with (
            patch.object(os, "name", "nt"),
            patch.dict(os.environ, fake_env, clear=True),
        ):
            env = _build_safe_env()
        # Look the keys up case-INSENSITIVELY. On a real Windows interpreter,
        # os.environ upper-cases every key on __setitem__ (see CPython os.py:
        # "Where Env Var Names Must Be UPPERCASE"), so patch.dict stores
        # "SystemRoot" as "SYSTEMROOT" there but leaves it mixed-case on POSIX.
        # Asserting on the literal mixed-case key would pass on Linux/macOS and
        # fail on Windows -- the one platform this test exists to protect.
        got = {k.upper(): v for k, v in env.items()}
        # cmd.exe essentials forwarded despite mixed case; secrets dropped.
        assert got.get("SYSTEMROOT") == r"C:\Windows"
        assert got.get("COMSPEC") == r"C:\Windows\System32\cmd.exe"
        assert "SECRET_API_KEY" not in got

    def test_build_safe_env_posix_unchanged(self):
        from amplifier_module_tool_skills.preprocessing import _build_safe_env

        fake_env = {"PATH": "/usr/bin", "HOME": "/home/x", "SECRET": "nope"}
        with (
            patch.object(os, "name", "posix"),
            patch.dict(os.environ, fake_env, clear=True),
        ):
            env = _build_safe_env()
        assert env == {"PATH": "/usr/bin", "HOME": "/home/x"}


class _FakeProc:
    """Stand-in for the asyncio subprocess whose communicate() times out."""

    def __init__(self) -> None:
        self.pid = 424242
        self.returncode = -9
        self.kill_calls = 0

    def kill(self) -> None:
        self.kill_calls += 1

    async def communicate(self):
        return (b"", b"")


def _drive_timeout(*, os_name: str, killpg_raises: type[BaseException] | None = None):
    """Drive _run_shell_command through its timeout branch and report what it killed.

    Returns (result_string, fake_proc, killpg_calls). No real process is spawned:
    create_subprocess_shell is stubbed and the 30s wait_for is forced to time out,
    so this exercises the real kill path in milliseconds on any platform.
    """
    import asyncio

    import amplifier_module_tool_skills.preprocessing as pp

    proc = _FakeProc()
    killpg_calls: list[tuple] = []

    def fake_killpg(pgid, sig):
        killpg_calls.append((pgid, sig))
        if killpg_raises is not None:
            raise killpg_raises()

    async def fake_create(*_args, **_kwargs):
        return proc

    real_wait_for = asyncio.wait_for

    async def fake_wait_for(awaitable, timeout=None):
        # Only hijack _run_shell_command's own 30s guard; let asyncio internals
        # use the real wait_for so patching stays confined to the code under test.
        if timeout == 30.0:
            awaitable.close()  # we never await it; avoids "never awaited" warning
            raise asyncio.TimeoutError
        return await real_wait_for(awaitable, timeout)

    with (
        patch.object(os, "name", os_name),
        patch.object(os, "killpg", fake_killpg, create=True),
        patch.object(os, "getpgid", lambda pid: pid, create=True),
        patch.object(asyncio, "create_subprocess_shell", fake_create),
        patch.object(asyncio, "wait_for", fake_wait_for),
    ):
        result = asyncio.run(pp._run_shell_command("sleep 999", Path(".")))

    return result, proc, killpg_calls


class TestTimeoutKillGuarded:
    """Bug 2: the timeout kill path must not call POSIX-only os.killpg on Windows.

    These assert on BEHAVIOUR (what the kill path actually calls), not on the
    source text. A source grep passes even if the guard lands in the wrong
    function, and breaks on a harmless refactor -- it tests the implementation
    instead of the contract.
    """

    def test_windows_timeout_kills_child_directly(self):
        result, proc, killpg_calls = _drive_timeout(os_name="nt")
        assert killpg_calls == [], "POSIX-only os.killpg was called on Windows"
        assert proc.kill_calls >= 1, "timed-out child was never killed on Windows"
        assert "timed out" in result

    def test_posix_timeout_still_kills_process_group(self):
        # No regression: POSIX keeps group-killing so shell-spawned grandchildren die.
        result, proc, killpg_calls = _drive_timeout(os_name="posix")
        assert len(killpg_calls) == 1, "POSIX no longer kills the process group"
        assert killpg_calls[0][1] == signal.SIGKILL
        assert proc.kill_calls == 0
        assert "timed out" in result

    def test_killpg_attribute_error_falls_back_to_proc_kill(self):
        # Simulates a real Windows interpreter, where os.killpg does not exist at
        # all: the AttributeError must be swallowed and the child killed anyway,
        # rather than escaping and orphaning it.
        result, proc, _ = _drive_timeout(os_name="posix", killpg_raises=AttributeError)
        assert proc.kill_calls >= 1, "AttributeError escaped and orphaned the child"
        assert "timed out" in result
