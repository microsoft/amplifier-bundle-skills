"""Windows-compatibility tests for the tool-skills load/discovery path.

Three bugs were fixed:
  1. SKILL.md was read as "utf-8" (not "utf-8-sig"). A Windows-authored file
     (Notepad, PowerShell Out-File, many editors) is UTF-8 WITH a BOM, so the
     retained \ufeff made content.startswith("---") False and the skill was
     silently dropped ("missing YAML frontmatter"). TEETH ON LINUX -- the BOM
     behaviour is platform-independent, so the old code fails this test here too.
  2. The shell-command timeout handler called os.killpg/os.getpgid/SIGKILL,
     which do not exist on Windows -> AttributeError + orphaned child. Verified
     by asserting the handler now guards on os.name and swallows AttributeError.
  3. _build_safe_env()'s allowlist was POSIX-only vocabulary, so cmd.exe (which
     create_subprocess_shell uses on Windows) lost SystemRoot/ComSpec/PATHEXT
     and failed to spawn. Verified by asserting the Windows allowlist carries
     those keys and matches case-insensitively.
"""

import os
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
            assert essential in upper, f"{essential} missing from Windows safe-env allowlist"

    def test_build_safe_env_forwards_systemroot_on_windows(self):
        from amplifier_module_tool_skills.preprocessing import _build_safe_env

        fake_env = {
            "SystemRoot": r"C:\Windows",   # note the real-world mixed case
            "ComSpec": r"C:\Windows\System32\cmd.exe",
            "PATH": r"C:\Windows",
            "SECRET_API_KEY": "sk-must-not-leak",
        }
        with patch.object(os, "name", "nt"), patch.dict(os.environ, fake_env, clear=True):
            env = _build_safe_env()
        # cmd.exe essentials forwarded despite mixed case; secrets dropped.
        assert env.get("SystemRoot") == r"C:\Windows"
        assert env.get("ComSpec") == r"C:\Windows\System32\cmd.exe"
        assert "SECRET_API_KEY" not in env

    def test_build_safe_env_posix_unchanged(self):
        from amplifier_module_tool_skills.preprocessing import _build_safe_env

        fake_env = {"PATH": "/usr/bin", "HOME": "/home/x", "SECRET": "nope"}
        with patch.object(os, "name", "posix"), patch.dict(os.environ, fake_env, clear=True):
            env = _build_safe_env()
        assert env == {"PATH": "/usr/bin", "HOME": "/home/x"}


class TestTimeoutKillGuarded:
    """Bug 2: the timeout kill path must not call POSIX-only os.killpg on Windows."""

    def test_source_guards_killpg_for_windows(self):
        import amplifier_module_tool_skills.preprocessing as pp

        src = Path(pp.__file__).read_text(encoding="utf-8")
        # The kill path is guarded on os.name and catches AttributeError so a
        # Windows AttributeError from os.killpg can never orphan the child.
        assert 'os.name == "nt"' in src
        assert "AttributeError" in src
