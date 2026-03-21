# amplifier-bundle-skills

Skills tool and Microsoft-curated skills collection for [Amplifier](https://github.com/microsoft/amplifier) agents, following the [Agent Skills specification](https://agentskills.io/).

## What This Does

Packages the [tool-skills](https://github.com/microsoft/amplifier-module-tool-skills) module with context instructions and a curated collection of reusable skills into composable behaviors for any Amplifier bundle.

## Behaviors

| Behavior | What you get | Use when |
|----------|-------------|----------|
| `skills:behaviors/skills` | Tool + instructions + curated skills | Default -- batteries included |
| `skills:behaviors/skills-tool` | Tool + instructions only | Your bundle brings its own skills |

## Curated Skills

| Skill | Description |
|-------|-------------|
| **image-vision** | LLM-based image analysis across multiple providers (Anthropic, OpenAI, Gemini, Azure) |
| **code-review** | Parallel code review — spawns 3 agents (code reuse, quality, efficiency) to review recent changes |
| **mass-change** | Parallel work orchestration — decomposes large changes into 5-30 independent units |
| **session-debug** | Session diagnostics — diagnoses misconfigured tools, failing operations, unexpected behavior |

### Power Skills

The `code-review`, `mass-change`, and `session-debug` skills are **power skills** — they use the enhanced skills format to run as isolated subagents with their own tool sets and model preferences. See [Enhanced Skills Format](#enhanced-skills-format) below.

## Quick Start

### As a standalone bundle

```bash
amplifier bundle add git+https://github.com/microsoft/amplifier-bundle-skills@main
```

### Compose into your bundle

Include the full behavior (tool + curated skills):

```yaml
includes:
  - bundle: git+https://github.com/microsoft/amplifier-bundle-skills@main
```

Or include just the tool (no curated skills):

```yaml
includes:
  - bundle: skills:behaviors/skills-tool
```

### Add your own skills alongside curated ones

If your bundle ships its own skills, declare them in your behavior YAML following the proven pattern from [amplifier-bundle-superpowers](https://github.com/microsoft/amplifier-bundle-superpowers):

```yaml
tools:
  - module: tool-skills
    source: git+https://github.com/microsoft/amplifier-module-tool-skills@main
    config:
      skills:
        - "git+https://github.com/microsoft/amplifier-bundle-skills@main#subdirectory=skills"
        - "git+https://github.com/your-org/your-bundle@main#subdirectory=skills"
```

> **Warning:** Do NOT use a top-level `skills:` key in your bundle frontmatter. The foundation layer does not process it -- skill sources placed there will be **silently ignored**. Always use the `tools:` config pattern shown above.

## Architecture

```
amplifier-bundle-skills/
├── bundle.md                     # Root bundle (includes foundation + full behavior)
├── behaviors/
│   ├── skills.yaml               # Full: tool + instructions + curated skills
│   └── skills-tool.yaml          # Minimal: just the tool + instructions
├── context/
│   └── skills-instructions.md    # Agent-facing skills system instructions
└── skills/
    ├── image-vision/             # LLM-based image analysis
    │   ├── SKILL.md
    │   └── ...
    ├── code-review/              # Parallel code review (power skill)
    │   └── SKILL.md
    ├── mass-change/              # Parallel work orchestration (power skill)
    │   └── SKILL.md
    └── session-debug/            # Session diagnostics (power skill)
        └── SKILL.md
```

**Design**: Two behaviors serve different consumers. The full behavior (`skills`) pre-configures the curated skills collection via `git+https://` URL. The minimal behavior (`skills-tool`) provides just the tool and instructions for bundles that manage their own skill sources.

## Enhanced Skills Format

Power skills use an enhanced SKILL.md frontmatter format that goes beyond the base Agent Skills specification:

| Field | Purpose |
|-------|---------|
| `context: fork` | Skill runs as an isolated subagent with its own conversation |
| `auto-load: true` | Skill activates at session start via embedded hooks |
| `disable-model-invocation: true` | User-invoked only (via `/command`), not triggered by the model |
| `model_role` | Semantic model selection via routing matrix (e.g., `coding`, `reasoning`, `critique`) |
| `allowed-tools` | Restricts which tools the subagent can use |
| `$ARGUMENTS`, `${SKILL_DIR}` | String substitution in skill body at load time |
| `` !`command` `` | Dynamic shell preprocessing — output is spliced into the skill content |

These features are implemented by the [tool-skills module](https://github.com/microsoft/amplifier-module-tool-skills). See its README for full format documentation.

## CLI Integration

Power skills register as slash commands and are available directly from the Amplifier CLI:

- `/code-review` — Run parallel code review on recent changes
- `/mass-change` — Decompose and execute a large change in parallel
- `/session-debug` — Diagnose session issues

These commands appear in `/help` and `/skills`. They are powered by the `SkillsDiscovery` capability exposed by the tool-skills module, which the CLI queries at startup to register user-invocable skills.

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

## License

MIT - See [LICENSE](LICENSE)
