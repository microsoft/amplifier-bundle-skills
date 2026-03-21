# Skills System

You have access to the skills system for loading domain knowledge packages.

## What Are Skills?

Skills are domain knowledge packages following the [Agent Skills specification](https://agentskills.io/specification). They provide structured information through progressive disclosure:

- **Level 1 (Metadata)**: Name + description (~100 tokens) - always visible via list/search
- **Level 2 (Content)**: Full markdown body (~1-5k tokens) - loaded on demand
- **Level 3 (References)**: Additional files (0 tokens until accessed via read_file)

## Skills Visibility

When skills are available, you'll see them automatically in your context before each request:

```
<available_skills>
Available skills (use load_skill tool):

- **python-testing**: Best practices for Python testing with pytest
- **git-workflow**: Git branching and commit message standards
- **api-design**: RESTful API design patterns and conventions
</available_skills>
```

You don't need to call `load_skill(list=true)` first - skills are made visible automatically through the visibility hook.

## Available Tool: load_skill

**Operations:**

- `load_skill(list=true)` - List all available skills
- `load_skill(search="pattern")` - Filter by keyword
- `load_skill(info="skill-name")` - Get metadata only
- `load_skill(skill_name="skill-name")` - Load full content

**Usage Examples:**

```
# List available skills (if not already visible)
load_skill(list=true)

# Search for specific skills
load_skill(search="python")

# Load a skill
load_skill(skill_name="example-skill")
```

## Enhanced Skills (Fork Execution)

Some skills use `context: fork` to run as isolated subagents. When you load a fork skill with `load_skill(skill_name="...")`, instead of returning content to inject into conversation, the skill:

1. Spawns a fresh subagent with its own context window
2. The skill's instructions become the subagent's task prompt
3. The subagent executes the task independently
4. The result is returned with a `response` field containing the subagent's output

**When you receive a fork skill result**, present the `response` content to the user. The response IS the work product — it contains the subagent's analysis, findings, or actions. Do not describe the metadata (`session_id`, `context`, `turn_count`) — present the actual response.

### Built-in Power Skills

Three power skills ship with the curated collection. These are user-invoked via slash commands and always fork:

| Skill | Slash Command | What It Does |
|-------|--------------|--------------|
| `code-review` | `/code-review [focus]` | Spawns 3 parallel review agents (code reuse, quality, efficiency) to review recent changes and apply fixes |
| `mass-change` | `/mass-change <instruction>` | Decomposes a large change into 5–30 independent units, spawns parallel agents to implement each |
| `session-debug` | `/session-debug [issue]` | Diagnoses session issues by delegating to the session-analyst agent |

These skills have `disable-model-invocation: true`, meaning they won't appear in the automatic skills visibility list. They are invoked by the user explicitly — via slash command (`/session-debug`, `/code-review`, `/mass-change`) or by calling `load_skill(skill_name="session-debug")` directly. When the user types one of these slash commands, load and execute the corresponding skill.

## Skills Discovery

Skills are discovered from these locations by default:
1. `.amplifier/skills/` (workspace)
2. `~/.amplifier/skills/` (user home)
3. `AMPLIFIER_SKILLS_DIR` environment variable

When multiple directories contain the same skill name, the first match wins (priority order matches the list order).

## Configuration

The skills tool supports custom directory configuration:

```yaml
tools:
  - module: tool-skills
    config:
      skills_dirs:
        - /custom/path/to/skills
        - /another/path
      visibility:
        enabled: true              # Show skills automatically (default: true)
        max_skills_visible: 50     # Limit for large collections (default: 50)
```

## Configuring Skills in Bundles

If your bundle ships its own skills or depends on community skills, configure them through the `tools:` section as module config for `tool-skills`:

```yaml
tools:
  - module: tool-skills
    source: git+https://github.com/microsoft/amplifier-module-tool-skills@main
    config:
      skills:
        - "git+https://github.com/my-org/my-skills-repo@main#subdirectory=skills"
        - "@mybundle:skills"
```

The `config.skills` list accepts three source types:

| Source type | Example | When to use |
|-------------|---------|-------------|
| Git URL | `git+https://github.com/org/repo@main#subdirectory=skills` | Remote community or shared skill repos |
| Bundle reference | `@mybundle:skills` | Skills shipped inside your own bundle |
| Local path | `/absolute/path/to/skills` | Development and testing |

Git URLs support an optional `#subdirectory=` fragment to point at a subfolder within the repo.

> **Warning:** Do NOT use a top-level `skills:` key in your bundle frontmatter. The foundation layer does not process it -- skill sources placed there will be **silently ignored**. Always use the `tools:` config pattern shown above.
