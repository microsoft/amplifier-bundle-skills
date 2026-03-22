# Agent Skills Spec Reference

Complete reference for the Agent Skills specification, Amplifier extensions, and Claude Code compatibility. Read this file when answering questions about skill frontmatter fields, loading behavior, shell preprocessing, string substitution, or model routing.

---

## Standard Fields

Standard fields are defined by the open [Agent Skills specification](https://agentskills.io) and are portable across harnesses that implement the spec.

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | **Required** | string | Unique skill identifier in kebab-case. Used as the shortcut name (e.g., `/name`) when `user-invocable: true`. Must be unique within the discovery scope. |
| `description` | **Required** | string | What the skill does and when to invoke it. Injected into the agent's routing context. Write for the agent reading it, not a human menu — be specific about trigger conditions. |
| `version` | Optional | string | Skill version string (e.g., `1.0.0`, `2.1.0`). Informational only — the harness does not enforce version constraints. Useful for changelogs and auditing. |
| `license` | Optional | string | SPDX license identifier (e.g., `MIT`, `Apache-2.0`). Informational only. Required for skills distributed in public bundles. |
| `compatibility` | Optional | string/object | Declares harness compatibility constraints (e.g., minimum harness version or required feature flags). Exact format is harness-defined. Informational in most implementations. |
| `metadata` | Optional | object | Arbitrary key-value pairs for skill-level metadata (e.g., `author`, `tags`, `category`). Not processed by the harness — available to tooling and registries. |

**Note:** Only `name` and `description` are required. All other standard fields are optional. Unrecognized fields are ignored by compliant harnesses.

### Experimental Fields (agentskills.io)

These fields are defined by the agentskills.io spec but are not yet required by compliant harnesses. Support varies across tools — see the [Compatibility Matrix](./compatibility-matrix.md) for details.

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `allowed-tools` | Optional | string | Space-separated list of tool names the forked context is permitted to use (e.g., `Read Grep Glob Bash`). Restricts the tool surface for security or focus. Only applies when `context: fork`. Harness support varies — not required by compliant harnesses. |
| `hooks` | Optional | object | Lifecycle hooks executed at specific points (e.g., `on_load`, `on_complete`). Exact hook names and behavior are harness-defined. Harness support varies — not required by compliant harnesses. |

---

## Enhanced Format Extensions

Amplifier and Claude Code add fields beyond the open standard. These fields are either Amplifier-specific or Claude Code-specific. Using Amplifier extensions in a pure Claude Code skill will cause the extra fields to be ignored (not error).

### Amplifier Extensions

These fields are specific to Amplifier's skill loading and execution model.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `context` | enum: `fork` | `null` | When set to `fork`, the skill runs in a fresh context window that does not inherit the caller's conversation history. The forked context receives only the skill body and the invocation arguments. Ideal for context-sink patterns, knowledge consultants, and orchestrators that must not be contaminated by prior conversation state. |
| `agent` | string | `null` | Specifies the agent bundle path to use for executing this skill. When set, Amplifier delegates execution to the named agent rather than running the skill body inline. Example: `foundation:explorer`. |
| `model_role` | string | `general` | Preferred model role for executing this skill in a forked context. Matched against the active routing matrix at invocation time. Common values: `general`, `reasoning`, `coding`, `critique`, `creative`. Only applies when `context: fork`. Has no effect in root context execution. |
| `provider_preferences` | list | `[]` | Ordered list of provider/model preferences for skill execution. Each entry is a `{provider, model}` pair, with glob pattern support for model names. Highest priority in the model selection chain. Only applies when `context: fork`. |
| `disable-model-invocation` | boolean | `false` | When `true`, the skill body is loaded as system prompt context but the model is NOT called in the root context. Used for orchestrator skills that are expected to immediately `delegate` to sub-agents. Prevents a wasted root-context model call for pure delegation patterns. |
| `user-invocable` | boolean | `false` | When `true`, registers the skill as a `/name` slash command that users can invoke directly in the chat interface. Also causes the skill to appear in `/skills` listings. The command name is the `name` field value. |
| `auto-load` | boolean | `false` | When `true`, the skill's body is automatically injected into the system prompt at every session startup. Use sparingly — auto-load skills are paid at every session start regardless of relevance. Only for always-active conventions or persistent project context. |

### Claude Code Extensions

Claude Code Skills 2.0 introduces its own extended fields. The table below maps Claude Code features to their Amplifier equivalents.

| Claude Code Feature | Claude Code Field | Amplifier Equivalent | Notes |
|---------------------|-------------------|----------------------|-------|
| Slash command registration | `user-invocable: true` in description prefix | `user-invocable: true` | Both register `/name` shortcuts. Amplifier uses explicit frontmatter; Claude Code uses a description convention. |
| Argument passing | `$ARGUMENTS` in body | `$ARGUMENTS` | Identical syntax — fully portable. |
| Positional arguments | `$1`, `$2`, ... in body | `$1`, `$2`, ... | Identical syntax — fully portable. |
| Skill directory reference | `${SKILL_DIR}` in body | `${SKILL_DIR}` | Identical syntax — fully portable. |
| Shell preprocessing | `!`command`` in body | `!`command`` | Identical syntax — fully portable. Amplifier executes at load time; Claude Code behavior is harness-specific. |
| Namespace isolation | N/A | `name` field scoping | Amplifier scopes names within discovery paths; Claude Code uses project-level naming. |
| MCP tool restriction | Tool permission settings | `allowed-tools` | Amplifier uses the `allowed-tools` frontmatter field. Claude Code uses separate MCP configuration. |

---

## Shell Preprocessing

Shell preprocessing allows a skill to embed the output of shell commands directly into its body at load time. This is useful for injecting dynamic context — file listings, environment info, timestamps, or configuration values — without hard-coding them.

### Syntax

Wrap a shell command in backticks preceded by `!`:

```
!`command`
```

Example:

```markdown
## Current Project Status

!`git log --oneline -5`

## Environment

!`node --version`
!`python --version`
```

### How It Works

1. **Execution at load time** — Shell preprocessing runs when the skill body is loaded into the context window, before the model sees the content. The output replaces the `!`command`` token inline.

2. **Sanitized environment** — Commands run in a restricted environment. The PATH is limited to standard system directories. User shell configuration (`.bashrc`, `.zshrc`, shell aliases) is not sourced. Environment variables from the caller's session are not inherited unless explicitly whitelisted.

3. **Timeout behavior** — Each shell command has a maximum execution timeout (typically 5–10 seconds depending on the harness). Commands that exceed the timeout are replaced with an error marker in the output: `[shell preprocessing error: timeout]`. Long-running commands or commands that block on I/O will fail.

4. **Failure handling** — If a command exits with a non-zero status, the output is replaced with an error marker. The skill continues loading — preprocessing failures do not prevent skill invocation.

### Security and Trust Model

Shell preprocessing introduces execution risk. Amplifier applies a trust model based on skill source:

- **Local skills** (`.amplifier/skills/`, `~/.amplifier/skills/`) — Preprocessing is enabled. These are author-controlled and treated as trusted.
- **Bundle skills** — Preprocessing is enabled. Bundle skills are distributed through known channels and reviewed.
- **Remote skills** (loaded from `git+https://` URLs) — Preprocessing behavior is configurable. By default, remote skills from unverified sources have shell preprocessing disabled or sandboxed. Users must explicitly grant trust to a remote source to enable preprocessing.

**Security implication:** Never load skills from untrusted remote sources without reviewing their content. A malicious `!`command`` could read credentials, exfiltrate data, or modify files.

---

## String Substitution

Amplifier substitutes special variables in the skill body before passing it to the model. Substitution happens after shell preprocessing.

| Variable | Description | Example |
|----------|-------------|---------|
| `$ARGUMENTS` | The full argument string passed by the user at invocation time. If the user runs `/my-skill review this file.py`, `$ARGUMENTS` is `review this file.py`. Empty string if no arguments provided. | `Analyze the following request: $ARGUMENTS` |
| `$1`, `$2`, ... | Positional arguments split from `$ARGUMENTS` on whitespace. `$1` is the first word, `$2` the second, and so on. Useful when the skill expects structured arguments (e.g., `/deploy staging v1.2.0`). | `Deploy environment: $1, Version: $2` |
| `${SKILL_DIR}` | Absolute path to the directory containing this `SKILL.md` file. Use when the skill body needs to reference companion files by absolute path (e.g., in shell preprocessing or `read_file` calls). | `read_file("${SKILL_DIR}/patterns.md")` |

### Usage Examples

**$ARGUMENTS — passing the full user request:**

```markdown
## Question

$ARGUMENTS

If no question was provided, ask the user what they need help with.
```

**$1, $2 — structured positional arguments:**

```markdown
## Task

Deploy **$1** environment to version **$2**.

If either argument is missing, output usage: `/deploy <env> <version>`
```

**${SKILL_DIR} — absolute path to companion files:**

```markdown
## Setup

Read the setup guide before proceeding:

!`cat "${SKILL_DIR}/setup.md"`
```

### Guard Patterns

Always guard against empty arguments when the skill requires input:

```markdown
$ARGUMENTS

<!-- Guard: if $ARGUMENTS is empty, output usage and stop -->
If the above is empty, respond with:
"Usage: /my-skill <topic>
Example: /my-skill REST API pagination patterns"
```

---

## Model Selection Precedence

When Amplifier selects which model to use for a forked skill context, it applies the following precedence chain from highest to lowest priority:

1. **`provider_preferences` field** *(highest priority)* — Explicit provider/model list in the skill's frontmatter. When present, Amplifier uses the first available provider/model pair from this list. This overrides all other selection mechanisms. Use when a skill requires a specific model capability (e.g., a vision model for image analysis tasks).

2. **`model_role` field** — Named role matched against the active routing matrix. The routing matrix maps role names to available provider/model pairs for the current session. Common roles: `general`, `reasoning`, `coding`, `critique`, `creative`, `vision`. The routing matrix is configured at the session or workspace level.

3. **Session-level model override** — The user or operator may have set a session-wide model preference via configuration or CLI flags. Session overrides apply to forked contexts unless `provider_preferences` or `model_role` is set in the frontmatter.

4. **Workspace default model** — The model configured as the default for the current workspace (via `settings.yaml` or environment variables). Applies when no skill-level or session-level selection has been made.

5. **System defaults** *(lowest priority)* — The harness's built-in fallback model selection. Used when no other preference has been expressed at any level.

**Recommendation:** For most skills, `model_role` is the right choice. It keeps skills portable across different provider configurations while still expressing the capability requirement (e.g., `reasoning` for architecture decisions, `critique` for code review). Use `provider_preferences` only when a skill genuinely requires a specific model that cannot be substituted — for example, a vision-capable model or a model fine-tuned for a domain task. Avoid hard-coding provider preferences in skills that will be shared across teams with different provider access.
