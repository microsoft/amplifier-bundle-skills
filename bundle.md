---
bundle:
  name: skills
  version: 1.0.0
  description: Skills tool and Microsoft-curated skills collection for Amplifier agents

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: skills:behaviors/skills
---

# Skills

Provides the [Agent Skills](https://agentskills.io/specification) system for Amplifier agents: the `load_skill` tool, automatic skills visibility, and a curated collection of Microsoft-maintained skills.

## Behaviors

| Behavior | What you get | Use when |
|----------|-------------|----------|
| `skills:behaviors/skills` | Tool + instructions + curated skills | Default -- batteries included |
| `skills:behaviors/skills-tool` | Tool + instructions only | Your bundle brings its own skills |

## Curated Skills

| Skill | Description |
|-------|-------------|
| **image-vision** | LLM-based image analysis across multiple providers (Anthropic, OpenAI, Gemini, Azure) |

## Usage

### Include the full behavior (recommended)

```yaml
includes:
  - bundle: git+https://github.com/microsoft/amplifier-bundle-skills@main
```

Or compose just the behavior:

```yaml
includes:
  - bundle: git+https://github.com/microsoft/amplifier-bundle-skills@main#path=behaviors/skills.yaml
```

### Include only the tool (no curated skills)

```yaml
includes:
  - bundle: git+https://github.com/microsoft/amplifier-bundle-skills@main#path=behaviors/skills-tool.yaml
```

### Add your own skills alongside curated ones

Bundles that include this behavior and also ship their own skills should declare additional skill sources in their own behavior YAML:

```yaml
tools:
  - module: tool-skills
    source: git+https://github.com/microsoft/amplifier-bundle-skills@main#subdirectory=modules/tool-skills
    config:
      skills:
        - "git+https://github.com/microsoft/amplifier-bundle-skills@main#subdirectory=skills"
        - "git+https://github.com/microsoft/your-bundle@main#subdirectory=skills"
```

> **URL fragments:** `#path=` selects a specific behavior file for `includes:`. `#subdirectory=` selects a directory subtree for module sources and skill discovery. They serve different purposes and are not interchangeable.

@skills:context/skills-instructions.md

---

@foundation:context/shared/common-system-base.md
