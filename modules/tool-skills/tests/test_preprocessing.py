"""Tests for preprocessing pipeline — string substitution and shell execution."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amplifier_module_tool_skills.preprocessing import (
    MAX_SHELL_OUTPUT_BYTES,
    preprocess,
)


@pytest.mark.asyncio
async def test_arguments_substitution():
    """$ARGUMENTS is replaced with the full argument string."""
    body = "Use these arguments: $ARGUMENTS"
    result = await preprocess(body, skill_dir=Path("/some/skill"), arguments="foo bar")
    assert result == "Use these arguments: foo bar"


@pytest.mark.asyncio
async def test_positional_substitution():
    """$0, $1, $2 are replaced with positional arguments."""
    body = "First: $0, Second: $1, Third: $2"
    result = await preprocess(
        body, skill_dir=Path("/some/skill"), arguments="alpha beta gamma"
    )
    assert result == "First: alpha, Second: beta, Third: gamma"


@pytest.mark.asyncio
async def test_skill_dir_substitution():
    """${SKILL_DIR} is replaced with the skill directory path."""
    body = "Skill lives at: ${SKILL_DIR}"
    skill_dir = Path("/path/to/my-skill")
    result = await preprocess(body, skill_dir=skill_dir, arguments=None)
    assert result == f"Skill lives at: {skill_dir}"


@pytest.mark.asyncio
async def test_missing_arguments_become_empty_string():
    """Missing/beyond-provided positional args and $ARGUMENTS with None become empty string."""
    body = "Args: $ARGUMENTS, Pos: $0, Missing: $1"
    result = await preprocess(body, skill_dir=Path("/some/skill"), arguments=None)
    assert result == "Args: , Pos: , Missing: "


@pytest.mark.asyncio
async def test_combined_substitutions():
    """Combined substitutions work together in a single body."""
    body = "Dir: ${SKILL_DIR}, All: $ARGUMENTS, First: $0"
    skill_dir = Path("/skills/my-skill")
    result = await preprocess(body, skill_dir=skill_dir, arguments="hello world")
    assert result == f"Dir: {skill_dir}, All: hello world, First: hello"


@pytest.mark.asyncio
async def test_body_without_markers_unchanged():
    """Body without any substitution markers passes through unchanged."""
    body = "This is plain text with no markers."
    result = await preprocess(body, skill_dir=Path("/some/skill"), arguments="ignored")
    assert result == "This is plain text with no markers."


@pytest.mark.asyncio
async def test_shell_command_execution(tmp_path):
    """!`command` patterns are executed and replaced with wrapped stdout output."""
    body = "Version: !`echo hello`"
    result = await preprocess(body, skill_dir=tmp_path, arguments=None)
    assert result == "Version: <shell-output>hello</shell-output>"


@pytest.mark.asyncio
async def test_shell_echo_hello_world(tmp_path):
    """!`echo hello-world` is replaced with wrapped 'hello-world' (hyphenated output)."""
    body = "!`echo hello-world`"
    result = await preprocess(body, skill_dir=tmp_path, arguments=None)
    assert result == "<shell-output>hello-world</shell-output>"


@pytest.mark.asyncio
async def test_shell_failed_command_injects_error(tmp_path):
    """Failed shell commands inject error inline with '[preprocessing error:' prefix."""
    body = "Result: !`exit 1`"
    result = await preprocess(body, skill_dir=tmp_path, arguments=None)
    assert "[preprocessing error:" in result


@pytest.mark.asyncio
async def test_shell_command_uses_skill_dir_as_cwd(tmp_path):
    """Shell commands execute with skill_dir as working directory (can cat files from there)."""
    # Write a file in the skill dir
    (tmp_path / "hello.txt").write_text("from-skill-dir\n")
    body = "!`cat hello.txt`"
    result = await preprocess(body, skill_dir=tmp_path, arguments=None)
    assert result == "<shell-output>from-skill-dir</shell-output>"


@pytest.mark.asyncio
async def test_shell_multiple_patterns_all_replaced(tmp_path):
    """Multiple !`command` patterns in a body are all replaced."""
    body = "A=!`echo alpha` B=!`echo beta`"
    result = await preprocess(body, skill_dir=tmp_path, arguments=None)
    assert (
        result
        == "A=<shell-output>alpha</shell-output> B=<shell-output>beta</shell-output>"
    )


@pytest.mark.asyncio
async def test_shell_commands_cannot_see_user_arguments(tmp_path):
    """Shell commands cannot see user arguments — $ARGUMENTS is substituted AFTER shell runs."""
    # With safe pipeline: shell runs `echo $ARGUMENTS` where $ARGUMENTS is an unset
    # shell env var (expands to empty string) — user's "world" never reaches the shell.
    body = "!`echo $ARGUMENTS`"
    result = await preprocess(body, skill_dir=tmp_path, arguments="world")
    assert "world" not in result
    # empty shell output → no wrapper (empty string returned)
    assert "<shell-output>" not in result


@pytest.mark.asyncio
async def test_user_variables_substituted_after_shell_execution(tmp_path):
    """$ARGUMENTS is substituted after shell execution — both work correctly together."""
    # Shell runs !`echo safe`, then $ARGUMENTS is substituted with user input
    body = "!`echo safe` and $ARGUMENTS"
    result = await preprocess(body, skill_dir=tmp_path, arguments="user-input")
    assert result == "<shell-output>safe</shell-output> and user-input"


@pytest.mark.asyncio
async def test_shell_injection_via_arguments_prevented(tmp_path):
    """Malicious arguments containing shell metacharacters cannot reach the shell.

    The injection vector is $ARGUMENTS embedded inside a !`...` shell pattern.
    With the OLD (unsafe) pipeline, $ARGUMENTS would be substituted before shell
    execution, turning !`echo hello$ARGUMENTS` into !`echo hello; echo INJECTED`,
    executing arbitrary commands. With the SAFE pipeline, the shell only sees
    `echo hello$ARGUMENTS` where $ARGUMENTS is an unset env var → empty string.
    """
    # $ARGUMENTS is inside the shell command — the classic injection vector
    body = "!`echo hello$ARGUMENTS`"
    malicious_args = "; echo INJECTED"
    result = await preprocess(body, skill_dir=tmp_path, arguments=malicious_args)
    # With safe pipeline: shell runs `echo hello` (ARGUMENTS env var is empty/unset)
    # → output is "hello". Injected command never executes.
    assert "INJECTED" not in result


@pytest.mark.asyncio
async def test_normal_backticks_not_affected(tmp_path):
    """Normal backticks like `code` are not treated as shell commands."""
    body = "Use `some_function()` in your code."
    result = await preprocess(body, skill_dir=tmp_path, arguments=None)
    assert result == "Use `some_function()` in your code."


@pytest.mark.asyncio
async def test_shell_commands_use_sanitized_environment(tmp_path, monkeypatch):
    """API keys and secrets are not visible to subprocesses spawned by shell commands."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-secret")
    body = "!`printenv ANTHROPIC_API_KEY 2>/dev/null || echo NOTSET`"
    result = await preprocess(body, skill_dir=tmp_path, arguments=None)
    assert "sk-secret-key" not in result
    assert "NOTSET" in result


@pytest.mark.asyncio
async def test_execute_shell_false_skips_shell_commands(tmp_path):
    """execute_shell=False prevents !`command` execution but keeps ${SKILL_DIR} substitution."""
    body = "Dir: ${SKILL_DIR}, Command: !`echo hello`"
    result = await preprocess(
        body, skill_dir=tmp_path, arguments=None, execute_shell=False
    )
    # Shell command NOT executed — pattern preserved as-is
    assert "!`echo hello`" in result
    # Variable substitution still happens
    assert str(tmp_path) in result


@pytest.mark.asyncio
async def test_shell_timeout_kills_process_group(tmp_path):
    """start_new_session=True is passed to create_subprocess_shell and timeout returns error."""
    # Create a mock process
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.kill = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    mock_create = AsyncMock(return_value=mock_proc)

    with patch("asyncio.create_subprocess_shell", mock_create):
        with patch("asyncio.wait_for", AsyncMock(side_effect=asyncio.TimeoutError)):
            result = await preprocess(
                "!`sleep 100`", skill_dir=tmp_path, arguments=None
            )

    # Verify start_new_session=True was passed to create_subprocess_shell
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs.get("start_new_session") is True

    # Verify result contains 'timed out'
    assert "timed out" in result


@pytest.mark.asyncio
async def test_shell_output_wrapped_in_delimiters(tmp_path):
    """Shell command output is wrapped in <shell-output>...</shell-output> delimiters."""
    body = "!`echo hello`"
    result = await preprocess(body, skill_dir=tmp_path, arguments=None)
    assert "<shell-output>" in result
    assert "</shell-output>" in result


@pytest.mark.asyncio
async def test_shell_output_truncated_at_max_size(tmp_path):
    """Shell output larger than MAX_SHELL_OUTPUT_BYTES is truncated with a notice."""
    # Create a file larger than the limit
    large_file = tmp_path / "large.bin"
    large_file.write_bytes(b"x" * (MAX_SHELL_OUTPUT_BYTES + 1000))
    body = "!`cat large.bin`"
    result = await preprocess(body, skill_dir=tmp_path, arguments=None)
    assert "[truncated" in result
    assert len(result) < MAX_SHELL_OUTPUT_BYTES + 500  # total length is bounded


@pytest.mark.asyncio
async def test_untrusted_skill_shell_commands_blocked(tmp_path):
    """trusted=False blocks shell commands — 'pwned' never executes."""
    body = "!`echo pwned`"
    result = await preprocess(body, skill_dir=tmp_path, arguments=None, trusted=False)
    assert "pwned" not in result
    assert "[untrusted skill" in result


@pytest.mark.asyncio
async def test_trusted_skill_shell_commands_execute(tmp_path):
    """trusted=True (default) executes shell commands normally."""
    body = "!`echo safe`"
    result = await preprocess(body, skill_dir=tmp_path, arguments=None, trusted=True)
    assert "<shell-output>safe</shell-output>" in result
