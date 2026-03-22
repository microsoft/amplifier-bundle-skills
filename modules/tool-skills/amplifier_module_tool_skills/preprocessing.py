"""Preprocessing pipeline for skill body content.

Handles string substitution and shell command execution in order:
1. System variable substitution (${SKILL_DIR}) — safe, platform-provided, runs BEFORE shell
2. Shell preprocessing (!`command` patterns) — gated by execute_shell
3. User variable substitution ($ARGUMENTS, positional $N) — user input, runs AFTER shell
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import signal
from pathlib import Path

logger = logging.getLogger(__name__)

# Matches !`command` patterns for shell execution
_SHELL_PATTERN = re.compile(r"!`([^`]+)`")

# Maximum allowed shell output size. Output beyond this is truncated to prevent
# large or adversarial command output from flooding the AI context window.
MAX_SHELL_OUTPUT_BYTES = 1_048_576  # 1 MB

# Only these environment variables are passed to subprocesses spawned by shell commands.
# This prevents API keys and secrets from leaking into subprocess environments.
_SAFE_ENV_KEYS: frozenset[str] = frozenset(
    {"PATH", "HOME", "TMPDIR", "LANG", "TERM", "USER", "SHELL", "LC_ALL"}
)


def _build_safe_env() -> dict[str, str]:
    """Build a minimal environment dict for subprocess execution.

    Returns only the keys in _SAFE_ENV_KEYS that are present in os.environ,
    preventing API keys and other secrets from leaking into subprocesses.

    Returns:
        Dict containing only the safe subset of the current environment.
    """
    return {k: v for k, v in os.environ.items() if k in _SAFE_ENV_KEYS}


def _substitute_system_variables(body: str, skill_dir: Path) -> str:
    """Replace system variable placeholders in body text.

    Runs BEFORE shell execution. Only safe, platform-provided variables.

    Replacements performed:
    - ${SKILL_DIR}  → absolute skill directory path

    Args:
        body: Raw skill body text.
        skill_dir: Path to the skill directory.

    Returns:
        Body with system variable placeholders substituted.
    """
    body = body.replace("${SKILL_DIR}", str(skill_dir))
    return body


def _substitute_user_variables(body: str, arguments: str | None) -> str:
    """Replace user variable placeholders in body text.

    Runs AFTER shell execution. Contains user input — must not reach the shell.

    Replacements performed:
    - $ARGUMENTS    → full argument string (empty string if None)
    - $0, $1, $2, … → individual positional args (empty string if beyond args)

    Args:
        body: Body text after shell execution.
        arguments: Full argument string passed by the user, or None.

    Returns:
        Body with user variable placeholders substituted.
    """
    args_str = arguments if arguments is not None else ""
    positional = args_str.split() if args_str else []

    # $ARGUMENTS
    body = body.replace("$ARGUMENTS", args_str)

    # Positional $N — replace from highest index down to avoid $1 matching inside $10
    def _replace_positional(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        return positional[idx] if idx < len(positional) else ""

    body = re.sub(r"\$(\d+)", _replace_positional, body)

    return body


async def _execute_shell_commands(body: str, skill_dir: Path) -> str:
    """Find !`command` patterns and replace them with command stdout.

    Commands execute with skill_dir as the working directory.
    On success, the pattern is replaced with trimmed stdout.
    On failure or timeout (30 s), an inline error message is injected.

    Args:
        body: Body text after system variable substitution.
        skill_dir: Path to the skill directory (used as cwd).

    Returns:
        Body with all !`command` patterns replaced.
    """
    matches = list(_SHELL_PATTERN.finditer(body))
    if not matches:
        return body

    # Process matches in reverse order to preserve string offsets
    for match in reversed(matches):
        command = match.group(1)
        replacement = await _run_shell_command(command, skill_dir)
        body = body[: match.start()] + replacement + body[match.end() :]

    return body


async def _run_shell_command(command: str, cwd: Path) -> str:
    """Execute a single shell command and return its output.

    Args:
        command: Shell command string to execute.
        cwd: Working directory for the command.

    Returns:
        Empty string if output is empty, otherwise ``<shell-output>...</shell-output>``-wrapped
        (and truncated at MAX_SHELL_OUTPUT_BYTES if over limit) stdout on success, or an inline
        error string on failure/timeout.
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=_build_safe_env(),
            start_new_session=True,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=30.0
            )
        except asyncio.TimeoutError:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            await proc.communicate()
            logger.warning(f"Shell command timed out: {command!r}")
            return f"[preprocessing error: command timed out: {command}]"

        if proc.returncode != 0:
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            logger.warning(
                f"Shell command failed (exit {proc.returncode}): {command!r} — {stderr_text}"
            )
            return f"[preprocessing error: command failed (exit {proc.returncode}): {command}]"

        output = stdout_bytes.decode(errors="replace").strip()
        if not output:
            return ""
        if (
            len(output) > MAX_SHELL_OUTPUT_BYTES
        ):  # len() approximates bytes for typical ASCII shell output
            output = (
                output[:MAX_SHELL_OUTPUT_BYTES]
                + f"[truncated — output exceeded {MAX_SHELL_OUTPUT_BYTES} bytes]"
            )
        return f"<shell-output>{output}</shell-output>"

    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Shell command error: {command!r} — {exc}")
        return f"[preprocessing error: {exc}]"


def _block_untrusted_shell(body: str) -> str:
    """Replace !`command` patterns with a blocked placeholder for untrusted skills.

    Called when execute_shell=True but trusted=False (i.e., skill is from a remote
    source). Prevents remote skill repos from executing arbitrary shell commands.

    Args:
        body: Body text that may contain !`command` patterns.

    Returns:
        Body with all !`command` patterns replaced by a blocked notice.
    """

    def _replace(match: re.Match[str]) -> str:
        command = match.group(1)
        logger.warning(f"Blocked shell command from untrusted skill: {command!r}")
        return "[untrusted skill — shell command blocked]"

    return _SHELL_PATTERN.sub(_replace, body)


async def preprocess(
    body: str,
    *,
    skill_dir: Path,
    arguments: str | None,
    execute_shell: bool = True,
    trusted: bool = True,
) -> str:
    """Preprocess skill body content through the full pipeline.

    Pipeline order:
    1. System variable substitution (${SKILL_DIR}) — safe, platform-provided
    2. Shell command execution (!`command` patterns) — only when execute_shell=True
       AND trusted=True. Untrusted (remote) skills have shell commands blocked.
    3. User variable substitution ($ARGUMENTS, $N positional) — user input, after shell

    This ordering prevents shell injection: user-supplied arguments are never
    present in the body when shell commands execute.

    Args:
        body: Raw skill body text.
        skill_dir: Path to the skill directory.
        arguments: Full argument string from the user, or None.
        execute_shell: If False, skip shell command execution (!`command` patterns).
            Default is True. Set to False for inline skills to prevent untrusted
            shell execution.
        trusted: If False, block shell commands instead of executing them.
            Default is True. Set to False for skills loaded from remote sources
            (git repos) to prevent arbitrary command execution.

    Returns:
        Preprocessed body text ready for delivery.
    """
    body = _substitute_system_variables(body, skill_dir)
    if execute_shell:
        if trusted:
            body = await _execute_shell_commands(body, skill_dir)
        else:
            body = _block_untrusted_shell(body)
    body = _substitute_user_variables(body, arguments)
    return body
