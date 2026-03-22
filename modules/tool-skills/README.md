# Amplifier Skills Tool Module

> **Note:** This module is now maintained inside [amplifier-bundle-skills](https://github.com/microsoft/amplifier-bundle-skills) at `modules/tool-skills/`. The [standalone amplifier-module-tool-skills repo](https://github.com/microsoft/amplifier-module-tool-skills) is deprecated. All URLs below reference this bundle repository.

Modular capability that adds skill-based domain knowledge loading to Amplifier bundles.

## Overview

This module provides a progressive disclosure knowledge system for Amplifier agents. Skills are reusable knowledge packages that provide specialized expertise, workflows, and best practices following the [Agent Skills](https://agentskills.io) open standard.

**What You Get:**
- 🛠️ **load_skill tool** - Load domain knowledge from skill packages
- 👁️ **Visibility hook** - Skills automatically shown to agent (no need to list first)
- 📚 **Multi-source support** - Load skills from multiple directories
- 🔄 **Progressive disclosure** - Three levels of knowledge depth
- 🔀 **Fork execution** (`context: fork`) - Skills run as isolated subagents with their own conversation
- ⚡ **Shell preprocessing** (`` !`command` ``) - Dynamic content injection with security hardening
- 🎯 **Model resolution** - 5-level precedence chain for semantic model selection
- 🪝 **Auto-load hooks** (`auto_load`) - Skills activate at mount time for always-on quality gates
- 🔍 **SkillsDiscovery** - Capability interface for CLI integration (slash commands)
- 🚫 **Invocation control** (`disable-model-invocation`, `user-invocable`) - Fine-grained skill activation

**Progressive Disclosure Levels:**
- **Level 1 (Metadata)**: Name + description (~100 tokens) - Always visible
- **Level 2 (Content)**: Full markdown body (~1-5k tokens) - Loaded on demand
- **Level 3 (References)**: Additional files (0 tokens until accessed)

## Prerequisites

- **Python 3.11+**
- **[UV](https://github.com/astral-sh/uv)** - Fast Python package manager

### Installing UV

```bash
# macOS/Linux/WSL
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Installation

### Recommended: Include the Behavior

Add skills capability to your bundle by including the behavior:

```yaml
---
bundle:
  name: my-bundle
  version: 1.0.0
  description: My custom bundle with skills support

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: git+https://github.com/microsoft/amplifier-bundle-skills@main#path=behaviors/skills.yaml
---

# Your bundle instructions...
```

**What this gives you:**
- ✅ Tool + hook configured correctly together
- ✅ Default skills directories (`.amplifier/skills/`, `~/.amplifier/skills/`)
- ✅ Visibility enabled (skills shown automatically to agent)
- ✅ Clean dependency chain (no redundant includes)

**Why this pattern?**
- You control your foundation version
- Explicit about what capabilities you're adding
- Gets both tool + hook working together

### Alternative: Standalone Bundle

You can also use the complete skills bundle directly:

```bash
# Add the bundle
amplifier bundle add git+https://github.com/microsoft/amplifier-bundle-skills@main

# Use it
amplifier bundle use skills
amplifier run "List available skills"
```

**Note:** The standalone bundle includes foundation and is useful for testing or quick experimentation, but the behavior inclusion pattern is recommended for production bundles.

## Quick Start

### 1. Add Skills to Your Bundle

```yaml
# your-bundle.md
includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: git+https://github.com/microsoft/amplifier-bundle-skills@main#path=behaviors/skills.yaml
```

### 2. Create Skills Directory

```bash
mkdir -p .amplifier/skills
```

### 3. Use Your Bundle

```bash
amplifier bundle use your-bundle.md
amplifier run "What skills are available?"
```

The agent will see available skills automatically - no need to call `load_skill(list=true)` first!

### 4. Optional: Add Community Skills

```bash
# Clone example skills repository
git clone https://github.com/anthropics/skills ~/community-skills

# Configure in settings.yaml (see Configuration section)
```

## Configuration

### Global Configuration (Recommended)

Add to `~/.amplifier/settings.yaml` to make skills available to **all bundles**:

```yaml
# Module source
sources:
  tool-skills: git+https://github.com/microsoft/amplifier-bundle-skills@main#subdirectory=modules/tool-skills

# Skills directories - applies to all bundles
skills:
  dirs:
    - ~/community-skills/skills   # Optional: Community skills collection
    - ~/.amplifier/skills         # User-specific skills
```

### Project-Specific Configuration

Add to `.amplifier/settings.local.yaml` for project-only skills:

```yaml
skills:
  dirs:
    - .amplifier/skills  # Project-specific skills (merged with global)
```

### Bundle-Level Override

Override skills directories in your bundle (if needed):

```yaml
# In your bundle YAML frontmatter
tools:
  - module: tool-skills
    config:
      skills_dirs:
        - .amplifier/skills          # Project skills
        - ~/community-skills/skills   # Community library
        - ~/my-custom-skills         # Your skills
      visibility:
        enabled: true                # Show skills automatically (default: true)
        max_skills_visible: 50       # Limit for large collections (default: 50)
```

### Configuration Priority

1. **Bundle config** (`skills_dirs` in tool config) - highest priority
2. **Settings.yaml** (`skills.dirs` in global/project settings) - recommended
3. **Defaults** (`.amplifier/skills`, `~/.amplifier/skills`, `$AMPLIFIER_SKILLS_DIR`) - fallback

### Remote Skills via Git URLs

Skills can be loaded directly from git repositories without cloning them locally. This enables sharing skills across teams and organizations.

**Supported formats:**

```yaml
skills:
  dirs:
    # Full repository as skills directory
    - git+https://github.com/anthropics/skills@main
    
    # Subdirectory within a repository
    - git+https://github.com/myorg/shared-skills@main#subdirectory=skills
    
    # Specific branch or tag
    - git+https://github.com/myorg/skills@v1.0.0
    
    # Mix local and remote sources
    - .amplifier/skills                    # Local project skills
    - ~/.amplifier/skills                  # Local user skills
    - git+https://github.com/team/skills@main  # Shared team skills
```

**Example: Using Community Skills**

Instead of cloning a repository locally:

```yaml
# In ~/.amplifier/settings.yaml
skills:
  dirs:
    - git+https://github.com/anthropics/skills@main  # Example community skills
    - ~/.amplifier/skills  # Your custom skills
```

**How it works:**

1. Git URLs are resolved and cached automatically on first use
2. Cache is stored in `~/.amplifier/cache/` with content-addressable naming
3. Subsequent loads use the cache (fast)
4. Update by clearing the cache: `rm -rf ~/.amplifier/cache/skills-*`

**Benefits:**

- No manual cloning or updating required
- Version pinning with `@tag` or `@commit`
- Subdirectory support for monorepos
- Automatic caching for performance

## Usage

### How Skills Appear to Agents

When skills are configured, agents see them automatically before each request:

```
<available_skills>
Available skills (use load_skill tool):

- **python-testing**: Best practices for Python testing with pytest
- **git-workflow**: Git branching and commit message standards
- **api-design**: RESTful API design patterns and conventions
</available_skills>
```

### The load_skill Tool

**Operations:**

1. **List skills**: `load_skill(list=true)` - Show all available skills
2. **Search skills**: `load_skill(search="pattern")` - Filter by keyword
3. **Get metadata**: `load_skill(info="skill-name")` - Metadata only
4. **Load content**: `load_skill(skill_name="skill-name")` - Full content

### Usage in Bundles

```markdown
---
bundle:
  name: module-creator
  description: Creates new Amplifier modules

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: git+https://github.com/microsoft/amplifier-bundle-skills@main#path=behaviors/skills.yaml
---

You are an Amplifier module creator.

Before creating modules:
1. Skills are visible automatically - review the available_skills list
2. Load relevant skills: load_skill(skill_name="module-development")
3. Follow the guidance from the skill
```

### Agent Workflow Example

```
User: "Create a new tool module for database access"

Agent sees: <available_skills> containing "module-development"

Agent calls: load_skill(skill_name="module-development")
Response: [Full guide with protocols, entry points, patterns]

Agent: Creates module following the skill's patterns
```

### Python API

```python
from amplifier_module_tool_skills import SkillsTool

# Create tool
tool = SkillsTool(config={}, coordinator=None)

# List all skills
result = await tool.execute({"list": True})
# Returns: {"message": "...", "skills": [{"name": "...", "description": "..."}]}

# Search for skills
result = await tool.execute({"search": "python"})
# Returns: {"message": "...", "matches": [{"name": "python-standards", ...}]}

# Get metadata
result = await tool.execute({"info": "python-standards"})
# Returns: {"name": "...", "description": "...", "version": "...", ...}

# Load skill content
result = await tool.execute({"skill_name": "python-standards"})
# Returns: {"content": "# python-standards\n\n...", "skill_directory": "/path/to/skill"}
```

## Creating Skills

### Skills Directory Structure

Skills follow the [Agent Skills format](https://agentskills.io/specification):

```
skills-directory/
├── design-patterns/
│   ├── SKILL.md          # Required: name and description in YAML frontmatter
│   └── examples/
│       └── module-pattern.md
├── python-standards/
│   ├── SKILL.md
│   ├── async-patterns.md
│   └── type-hints.md
└── module-development/
    └── SKILL.md
```

### SKILL.md Format

Skills use YAML frontmatter with markdown body:

```markdown
---
name: skill-name  # Required: unique identifier (lowercase with hyphens)
description: What this skill does and when to use it  # Required
version: 1.0.0
license: MIT
metadata:  # Optional
  category: development
  complexity: medium
---

# Skill Name

Instructions the agent follows when skill is loaded.

## Quick Start

[Minimal example to get started]

## Detailed Instructions

[Step-by-step guidance]

## Examples

[Concrete examples]
```

**Required fields:** `name` and `description` in YAML frontmatter  
**Format:** See [Agent Skills specification](https://agentskills.io/specification)

#### Enhanced Frontmatter Fields

Beyond the base spec, the following fields enable advanced skill behaviors:

```yaml
---
name: my-power-skill
description: An advanced skill with enhanced features

# Execution model
context: fork                  # Run as isolated subagent (own conversation + tools)

# Agent and model selection
agent: Explore | Plan | general-purpose  # Target agent type
model_role: coding | fast | reasoning | critique | general  # Semantic model routing
provider_preferences:          # Explicit model override
  - provider: anthropic
    model: claude-sonnet-4-20250514

# Invocation control
disable-model-invocation: true  # Not triggered by model — user-invoked only (via /command)
user-invocable: true            # Registers as a slash command in the CLI
auto-load: true                 # Activates at session start (for hook-based skills)

# Tool scoping
allowed-tools: Read Grep Glob Bash  # Restrict subagent's available tools
---
```

| Field | Purpose |
|-------|---------|
| `context: fork` | Skill runs as an isolated subagent with its own conversation |
| `agent` | Target agent archetype for routing |
| `model_role` | Semantic role for model selection via the routing matrix |
| `provider_preferences` | Explicit provider/model override (highest precedence) |
| `disable-model-invocation` | Prevents the model from loading the skill autonomously |
| `user-invocable` | Registers the skill as a `/command` in the CLI |
| `auto-load` | Skill activates at session start via embedded hooks |
| `allowed-tools` | Restricts which tools the forked subagent can access |

### Creating a Simple Skill

```bash
mkdir -p .amplifier/skills/my-skill
cat > .amplifier/skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: Does something useful. Use when you need X.
version: 1.0.0
license: MIT
---

# My Skill

## Purpose

[What this skill does]

## Usage

[How to use it]

## Examples

[Complete examples]
EOF
```

### Creating a Skill with References

```bash
mkdir -p .amplifier/skills/advanced-skill
cd .amplifier/skills/advanced-skill

# Main skill file
cat > SKILL.md << 'EOF'
---
name: advanced-skill
description: Advanced patterns
---

# Advanced Skill

## Quick Start

[Brief example]

## Detailed Guides

- See patterns.md for design patterns
- See examples.md for complete examples
EOF

# Reference files (loaded on-demand by agent using read_file)
echo "# Patterns Guide" > patterns.md
echo "# Examples" > examples.md
```

## Module Contract

**Module Type:** Tool  
**Mount Point:** `tools`  
**Entry Point:** `amplifier_module_tool_skills:mount`

## Security

The module applies defense-in-depth hardening for skill execution:

- **Sanitized subprocess environment** — Shell preprocessing (`` !`command` ``) runs with API keys and secrets stripped from the environment
- **Process group isolation** — Timed-out shell commands kill the entire process group, not just the parent
- **Trust gate for remote skills** — Remote skill sources (`git+https://`) are validated before execution
- **Shell output wrapping and truncation** — Subprocess output is bounded to prevent context overflow
- **HTTPS-only for remote sources** — Plain HTTP git URLs are rejected
- **Symlink boundary checking** — Skill file access is confined to the repository root boundary

## auto_load

Skills with `auto-load: true` (or `auto_load: true`) in their frontmatter activate automatically when the skills module mounts. This enables always-on, hook-based quality gates that run without explicit user invocation.

**Use case:** A skill that injects a pre-response quality check or coding standard reminder at the start of every session, without the user needing to load it manually.

```yaml
---
name: quality-gate
description: Always-on quality check
auto-load: true
---

[Hook content that activates at session start]
```

When the tool-skills module mounts, it scans all skill sources for `auto_load` skills and registers their content as session hooks.

## Testing

```bash
# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_tool.py::test_list_skills -v

# Run with coverage
uv run pytest --cov
```

## Local Development

### For Module Developers

If you're developing the tool-skills module itself:

**Option 1: Source Override (Recommended)**

```bash
# Add to ~/.amplifier/settings.yaml
sources:
  tool-skills: file:///absolute/path/to/amplifier-module-tool-skills
```

**Option 2: Workspace Convention**

```bash
# In your development workspace
mkdir -p .amplifier/modules
ln -s /path/to/amplifier-module-tool-skills .amplifier/modules/tool-skills
```

**Option 3: Environment Variable (Temporary)**

```bash
export AMPLIFIER_MODULE_TOOL_SKILLS=/path/to/amplifier-module-tool-skills
amplifier run "test"
```

### Testing Your Changes

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Format and check code
uv run ruff check .
uv run ruff format .

# Type checking
uv run pyright
```

## Dependencies

- `amplifier-core` - Core protocols and types
- `pyyaml>=6.0` - YAML parsing

## Examples

See `examples/skills-example.md` for a complete working example showing:
- How to include the skills behavior in your bundle
- How to customize skills directories
- Why direct behavior inclusion is recommended
- Complete bundle structure

## Contributing

> [!NOTE]
> This project is not currently accepting external contributions, but we're actively working toward opening this up. We value community input and look forward to collaborating in the future. For now, feel free to fork and experiment!

Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
