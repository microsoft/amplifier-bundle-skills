# Agent Skills Compatibility Matrix

Cross-harness reference for the Agent Skills specification. Use this file when answering questions about which features are portable, which are tool-specific, and how to write skills that work across multiple AI coding tools.

---

## Feature Support Matrix

The table below shows which features are supported by each tool. ✅ = supported, ❌ = not supported, ⚠️ = partial or harness-specific behavior.

| Feature | Amplifier | GitHub Copilot | Claude Code | OpenAI Codex |
|---------|:---------:|:--------------:|:-----------:|:------------:|
| **Standard Fields** | | | | |
| `name` | ✅ | ✅ | ✅ | ✅ |
| `description` | ✅ | ✅ | ✅ | ✅ |
| `version` | ✅ | ✅ | ✅ | ✅ |
| `license` | ✅ | ✅ | ✅ | ✅ |
| `compatibility` | ✅ | ✅ | ✅ | ✅ |
| `metadata` | ✅ | ✅ | ✅ | ✅ |
| **Experimental (agentskills.io)** | | | | |
| `allowed-tools` | ✅ | ❌ | ⚠️ | ❌ |
| `hooks` | ✅ | ❌ | ❌ | ❌ |
| **Amplifier Extensions** | | | | |
| `context: fork` | ✅ | ❌ | ❌ | ❌ |
| `model_role` | ✅ | ❌ | ❌ | ❌ |
| `provider_preferences` | ✅ | ❌ | ❌ | ❌ |
| `disable-model-invocation` | ✅ | ❌ | ❌ | ❌ |
| `user-invocable` | ✅ | ❌ | ✅ | ❌ |
| `auto-load` | ✅ | ❌ | ❌ | ❌ |
| `agent` | ✅ | ❌ | ❌ | ❌ |
| **String Substitution & Preprocessing** | | | | |
| `$ARGUMENTS` | ✅ | ❌ | ✅ | ❌ |
| `$1` (positional args) | ✅ | ❌ | ✅ | ❌ |
| `${SKILL_DIR}` | ✅ | ❌ | ✅ | ❌ |
| Shell preprocessing (`!`cmd``) | ✅ | ❌ | ✅ | ❌ |
| **Interaction Patterns** | | | | |
| Slash commands (`/name`) | ✅ | ❌ | ✅ | ❌ |
| Companion files | ✅ | ✅ | ✅ | ✅ |
| Discovery paths | ✅ | ✅ | ✅ | ✅ |
| Model selection | ✅ | ❌ | ❌ | ❌ |

**Key:** Standard fields (`name`, `description`, `version`, `license`, `compatibility`, `metadata`) are defined by the [agentskills.io](https://agentskills.io) open specification and are portable across all compliant harnesses. All other features are tool-specific extensions. `allowed-tools` and `hooks` are experimental fields in the agentskills.io spec — they are defined but not yet required by compliant harnesses, and support varies.

---

## Discovery Paths by Tool

Each tool discovers skills from specific directories. The table below shows the default paths for each tool.

| Tool | Project-Level Path | User-Level Path | Environment Variable |
|------|--------------------|-----------------|----------------------|
| **Amplifier** | `.amplifier/skills/` | `~/.amplifier/skills/` | `AMPLIFIER_SKILLS_DIR` |
| **GitHub Copilot** | `.github/copilot/` | N/A | N/A |
| **Claude Code** | `.claude/commands/` | `~/.claude/commands/` | N/A |
| **OpenAI Codex** | `.codex/skills/` | N/A | N/A |

**Notes:**
- Amplifier supports three discovery paths with priority: `AMPLIFIER_SKILLS_DIR` env var > project-level > user-level.
- GitHub Copilot reads Markdown instructions from `.github/copilot/` at the project level.
- Claude Code Skills 2.0 discovers skills (commands) from `.claude/commands/` project-level and `~/.claude/commands/` user-level.
- OpenAI Codex uses `.codex/skills/` for project-local skill definitions (path subject to change as the tool evolves).

---

## Writing Portable Skills

Skills written using only the base Agent Skills specification will load correctly in any compliant harness. This section explains how to write and organize skills for maximum portability.

### Stick to the Base Spec

For skills you want to share across tools, use only the fields defined by the [agentskills.io](https://agentskills.io) open standard:

- `name` — unique kebab-case identifier
- `description` — trigger conditions and purpose
- `version` — informational version string
- `license` — SPDX license identifier
- `compatibility` — harness constraints
- `metadata` — arbitrary key-value pairs
- `allowed-tools` — tool restriction list (experimental — where supported)
- `hooks` — lifecycle hooks (experimental — where supported)

A skill using only these standard fields will be recognized by any harness that implements the spec. Unrecognized fields are silently ignored by compliant harnesses, so including Amplifier extensions in a Claude Code skill will not cause errors — but those fields will have no effect.

### Avoid Tool-Specific Extensions

Amplifier extensions like `context: fork`, `model_role`, `provider_preferences`, `disable-model-invocation`, `auto-load`, and `agent` are powerful within Amplifier but are not part of the open specification.

Similarly, Amplifier-specific shell preprocessing (`!`command``) and model routing options have no equivalent in GitHub Copilot or OpenAI Codex.

**Non-portable frontmatter example (avoid in shared skills):**

```yaml
---
name: my-skill
description: Analyzes code structure
context: fork          # Amplifier-only — ignored by other tools
model_role: reasoning  # Amplifier-only — ignored by other tools
auto-load: false       # Amplifier-only — ignored by other tools
---
```

If you use these fields, the skill still loads in other harnesses — but the enhanced behavior (forked context, model routing) will not apply. Design the skill body to work without those capabilities for full portability.

### Use Companion Files Not Shell Preprocessing

Shell preprocessing (`!`command``) injects dynamic content at load time and is supported by Amplifier and Claude Code. However, it is not supported by GitHub Copilot, OpenAI Codex, or other harnesses.

**Preferred pattern: companion files**

Companion files (Markdown files placed alongside `SKILL.md`) work everywhere. Instead of injecting content via shell preprocessing, place static reference content in a companion file and instruct the model to read it:

```markdown
## Setup

Read the project configuration before proceeding:

read_file("${SKILL_DIR}/config-reference.md")
```

This pattern works in any harness because `read_file` is a model instruction, not a preprocessing directive. Shell preprocessing only works in Amplifier — companion files work everywhere.

**When shell preprocessing is acceptable:** Use `!`command`` only in Amplifier-specific skills where dynamic injection (e.g., `git log`, `node --version`) genuinely adds value and portability is not a goal.

### Cross-Harness Symlink Pattern

Rather than copying skills into each tool's discovery path, create a single canonical skills directory and symlink it into each tool's expected location. This ensures skills stay in sync and are managed in one place.

```bash
# Create a canonical skills directory at the project root
mkdir -p skills/

# Symlink into Amplifier's discovery path
mkdir -p .amplifier/
ln -s ../../skills .amplifier/skills

# Symlink into Claude Code's discovery path
mkdir -p .claude/
ln -s ../../skills .claude/commands

# Symlink into GitHub Copilot's discovery path
mkdir -p .github/
ln -s ../../skills .github/copilot
```

**Notes:**
- Use relative symlink paths (`../../skills`) to keep the repository self-contained.
- Each tool discovers the skills from its expected path, but all tools read the same `skills/` directory.
- Add `skills/` to version control and add the tool-specific paths (`.amplifier/skills`, `.claude/commands`, `.github/copilot`) to `.gitignore` if you prefer, or commit the symlinks directly.

### Portable Skill Template

The template below uses only standard fields from the [agentskills.io](https://agentskills.io) specification. This skill will load in any harness that implements the spec.

```markdown
---
name: my-portable-skill
description: "Describe what this skill does and when to invoke it. Write for the agent that will route to it — be specific about trigger conditions and use cases."
version: 1.0.0
license: MIT
metadata:
  author: your-name
  tags: [example, portable]
---

# My Portable Skill

## Task

$ARGUMENTS

If no arguments were provided, ask the user what they need help with.

## Instructions

1. Read the user's request from `$ARGUMENTS` above.
2. Perform the task.
3. Summarize what you did.
```

**What makes this portable:**
- Uses only `name`, `description`, `version`, `license`, and `metadata` — all standard fields.
- Uses `$ARGUMENTS` for input — supported by Amplifier and Claude Code; gracefully degrades in harnesses that do not support string substitution (the literal `$ARGUMENTS` text will appear, which the model can handle).
- No `context: fork`, `model_role`, `auto-load`, or other Amplifier extensions.
- No shell preprocessing — body content is static.
- Companion files (if needed) should be placed alongside `SKILL.md` and referenced via `read_file`.
