"""Parent-conversation context inheritance for fork skills.

A fork skill spawns a fresh sub-session with no conversation history. By
default that is exactly what we want (a clean slate). But a caller can opt
into inheriting some of the parent conversation, using the same two-axis
model the ``delegate`` tool exposes:

    context_depth  -> HOW MUCH:  "none" | "recent" | "all"
    context_scope  -> WHICH:     "conversation" | "agents" | "full"

The transforms below are intentionally a faithful mirror of the logic in
``amplifier_module_tool_delegate`` so that a fork skill and a delegate call
inherit context identically. They are kept as pure functions (no coordinator
state) so they are trivial to test and so this module stays a self-contained
brick with no dependency on the delegate package.

The selected/sanitized messages are rendered to a text block and prepended to
the skill body before it is handed to the spawned sub-session as its first
user turn. This matches how ``delegate`` injects parent context: as a text
preamble, not as replayed conversation turns.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Valid values, exposed so the tool schema and validation share one source.
VALID_DEPTHS = ("none", "recent", "all")
VALID_SCOPES = ("conversation", "agents", "full")

DEFAULT_DEPTH = "none"
DEFAULT_SCOPE = "conversation"
DEFAULT_TURNS = 5

# Content block types that are never human-readable conversation text.
_FILTERED_BLOCK_TYPES = {
    "tool_use",
    "tool_call",
    "tool_result",
    "thinking",
    "redacted_thinking",
}


def extract_recent_turns(
    messages: list[dict[str, Any]], n_turns: int
) -> list[dict[str, Any]]:
    """Return the last ``n_turns`` user->assistant turns.

    A "turn" starts at a user message and runs until the next user message.
    """
    if not messages or n_turns <= 0:
        return []

    turn_starts = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    if not turn_starts:
        return messages  # No user turns; nothing to slice on.
    if len(turn_starts) <= n_turns:
        return messages  # Fewer turns than requested; return all.

    start_index = turn_starts[-n_turns]
    return messages[start_index:]


def sanitize_content(content: Any) -> str:
    """Extract human-readable text from a message ``content`` field.

    Handles both the plain-string and list-of-blocks shapes; drops tool and
    reasoning blocks.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type == "text":
                    text = block.get("text", "")
                    if text:
                        text_parts.append(text)
                elif block_type not in _FILTERED_BLOCK_TYPES:
                    logger.debug("Unknown content block type '%s'", block_type)
            elif isinstance(block, str):
                text_parts.append(block)
        if text_parts:
            return "\n".join(text_parts)

    return ""


def _sanitize_conversation_only(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep only user/assistant conversation text; strip all tool content."""
    sanitized: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "tool" or msg.get("tool_call_id"):
            continue
        if role in ("user", "assistant"):
            if role == "assistant" and msg.get("tool_calls") and not msg.get("content"):
                continue
            text = sanitize_content(msg.get("content", ""))
            if text:
                sanitized.append({"role": role, "content": text})
    return sanitized


def _sanitize_with_agent_results(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Conversation text plus results from agent tools (delegate/task)."""
    sanitized: list[dict[str, Any]] = []
    agent_tools = {"delegate", "task"}
    for msg in messages:
        role = msg.get("role")
        if role == "tool":
            tool_name = msg.get("name", "")
            if tool_name in agent_tools:
                content = msg.get("content", "")
                if content:
                    sanitized.append(
                        {
                            "role": "assistant",
                            "content": f"[Agent Result from {tool_name}]: {content}",
                        }
                    )
            continue
        if msg.get("tool_call_id"):
            # OpenAI-shaped tool result; tool name not recoverable here.
            continue
        if role in ("user", "assistant"):
            if role == "assistant" and msg.get("tool_calls") and not msg.get("content"):
                continue
            text = sanitize_content(msg.get("content", ""))
            if text:
                sanitized.append({"role": role, "content": text})
    return sanitized


def _sanitize_all_content(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Conversation text plus all tool results (truncated)."""
    sanitized: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "tool":
            tool_name = msg.get("name", "unknown")
            content = msg.get("content", "")
            if content:
                if len(content) > 4000:
                    content = content[:4000] + "... [truncated]"
                sanitized.append(
                    {
                        "role": "assistant",
                        "content": f"[Tool Result from {tool_name}]: {content}",
                    }
                )
            continue
        if msg.get("tool_call_id"):
            continue
        if role in ("user", "assistant"):
            if role == "assistant" and msg.get("tool_calls") and not msg.get("content"):
                continue
            text = sanitize_content(msg.get("content", ""))
            if text:
                sanitized.append({"role": role, "content": text})
    return sanitized


def build_inherited_context(
    messages: list[dict[str, Any]] | None,
    depth: str,
    turns: int,
    scope: str,
) -> list[dict[str, Any]] | None:
    """Select and sanitize parent ``messages`` by depth (how much) and scope (which).

    ``messages`` is the raw parent history (already fetched by the caller).
    Returns the sanitized messages, or ``None`` when nothing should be
    inherited (depth "none", or no parent messages available).
    """
    if depth == "none":
        return None
    if not messages:
        return None

    # Step 1: depth filter.
    if depth == "recent":
        messages = extract_recent_turns(messages, turns)
    # "all" -> unchanged.

    # Step 2: scope filter.
    if scope == "conversation":
        return _sanitize_conversation_only(messages)
    if scope == "agents":
        return _sanitize_with_agent_results(messages)
    return _sanitize_all_content(messages)


def format_parent_context(messages: list[dict[str, Any]]) -> str:
    """Render sanitized parent messages as a text block to prepend to a skill body."""
    if not messages:
        return ""

    lines = [
        "[PARENT CONVERSATION CONTEXT]",
        "The following is conversation history inherited from the parent session:",
        "",
    ]
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        role_label = (
            "USER"
            if role == "user"
            else "ASSISTANT"
            if role == "assistant"
            else role.upper()
        )
        if len(content) > 2000:
            content = content[:2000] + "... [truncated]"
        lines.append(f"{role_label}: {content}")
        lines.append("")
    lines.append("[END PARENT CONTEXT]")
    return "\n".join(lines)
