---
name: session-debug
description: "Diagnose issues in the current Amplifier session — misconfigured tools, failing operations, unexpected behavior. Use when something isn't working right."
context: fork
disable-model-invocation: true
user-invocable: true
model_role: general
allowed-tools: Read Grep Glob Bash
---

# Debug: Session Diagnostics

Help the user diagnose an issue they're encountering in their current Amplifier session.

## Issue Description

$ARGUMENTS

If no issue was described, read the session logs and summarize any errors, warnings, or notable issues.

## Instructions

1. **Delegate to the session-analyst agent** to investigate the current session. The session-analyst has specialized knowledge for safely analyzing large event logs (events.jsonl files can contain lines with 100k+ tokens that will crash other tools). Use the delegate tool to dispatch it with the issue description and any relevant context.

2. **Check session configuration.** Review the current session's configuration for common issues:
   - Bundle composition problems (missing modules, failed loads)
   - Provider configuration (missing API keys, wrong endpoints)
   - Tool availability (tools expected but not mounted)
   - Hook failures (hooks that errored during lifecycle events)

   Session and project settings are typically at:
   - Project: `.amplifier/settings.yaml`
   - User: `~/.amplifier/settings.yaml`
   - Keys: `~/.amplifier/keys.env`

3. **Check for common patterns:**
   - Tool calls returning errors repeatedly
   - Provider rejections (rate limits, auth failures, model not found)
   - Module mount failures at startup
   - Context overflow or compaction issues

4. **Explain what you found in plain language.** Avoid jargon. Tell the user:
   - What went wrong
   - Why it likely happened
   - Concrete steps to fix it

5. **If the issue can't be diagnosed from logs alone**, suggest the user:
   - Run `amplifier doctor` for a system health check
   - Check `amplifier module list` to verify module availability
   - Try `amplifier --verbose` to see detailed startup output
