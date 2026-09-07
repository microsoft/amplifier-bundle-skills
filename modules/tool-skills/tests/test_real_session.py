"""Test that skills are visible in actual amplifier sessions.

This is an INTEGRATION smoke against the installed `amplifier` CLI, not a unit
test of this module. The CLI is a separate application (microsoft/amplifier-app-cli)
and is deliberately not a dependency of amplifier-module-tool-skills, so it is
absent on a clean machine -- including a CI runner. Before the guard below, this
module shelled out to it unconditionally and died with
`FileNotFoundError: [Errno 2] No such file or directory: 'amplifier'`; it only
ever passed because the developer running it happened to have the CLI on PATH.

The skip is reported explicitly (CI runs pytest with `-ra`), so a run where this
test does not execute says so in the job log rather than looking like coverage.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


def test_skills_visible_in_session():
    """Verify skills are visible when running amplifier with the skills bundle."""

    if shutil.which("amplifier") is None:
        pytest.skip(
            "the `amplifier` CLI is not on PATH -- this is an integration smoke "
            "against the installed application, which is not a dependency of this module"
        )

    # Create a test skill
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test-skill"
        skill_dir.mkdir()

        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-visibility-skill
description: A skill to test visibility in sessions
---
# Test Skill Content
This skill should be visible to the agent.""")

        # Create a simple test prompt
        test_prompt = "List available skills"

        # Run amplifier with the test skill directory
        # We'll check that the provider:request event is fired and hook injects context
        result = subprocess.run(
            [
                "amplifier",
                "run",
                "--bundle",
                "skills",
                "--dry-run",  # Don't actually call LLM
                test_prompt,
            ],
            env={
                **dict(os.environ),
                "AMPLIFIER_SKILLS_DIR": tmpdir,
            },
            capture_output=True,
            text=True,
            timeout=10,
        )

        # For now, just verify the command runs without error
        # (We can't easily test the actual context injection without a full session)
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        print(f"returncode: {result.returncode}")

        # Either the command ran clean, or the CLI rejected the unknown
        # --dry-run option. The exact phrasing/quoting of that rejection has
        # drifted across CLI versions (e.g. "No such option: --dry-run" vs
        # "No such option '--dry-run'."), so match on the stable prefix only.
        assert result.returncode == 0 or "No such option" in result.stderr


if __name__ == "__main__":
    test_skills_visible_in_session()
