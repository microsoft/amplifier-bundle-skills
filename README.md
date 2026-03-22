# amplifier-bundle-skills

Skills tool and Microsoft-curated skills collection for [Amplifier](https://github.com/microsoft/amplifier) agents, following the [Agent Skills specification](https://agentskills.io/).

## Vision

This repository pursues five goals:

1. Track the [Agent Skills standard](https://agentskills.io/) as it evolves, maintaining compatibility with specification updates.
2. Support Anthropic Skills 2.0 and emerging multi-provider skill formats as the ecosystem grows.
3. Welcome broader community contributions as the skills ecosystem matures beyond Microsoft-curated content.
4. Demonstrate lightweight agents-as-skills using the enhanced fork execution format (`context: fork`).
5. Provide practical skills-vs-agents guidance to help developers choose the right tool for their use case.

## What This Does

Packages the tool-skills module (at `modules/tool-skills/`) with context instructions and a curated collection of reusable skills into composable behaviors for any Amplifier bundle. The tool-skills module is now maintained in this repository; the [standalone amplifier-module-tool-skills repo](https://github.com/microsoft/amplifier-module-tool-skills) is deprecated.

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
| **skills-assist** | Skills expert — authoritative consultant for authoring, spec, compatibility, and skills-vs-agents guidance |

### Power Skills

The `code-review`, `mass-change`, and `session-debug` skills are **power skills** — they use the enhanced skills format to run as isolated subagents with their own tool sets and model preferences. Power skills set `disable-model-invocation: true`, meaning they are user-invoked only (via `/command`) and will not trigger automatically when the LLM processes context. See [Enhanced Skills Format](#enhanced-skills-format) below.

### Expert Skills

The `skills-assist` skill is an **expert skill** — it uses `context: fork` to run in a clean context window as an isolated knowledge consultant, but it is not a delegating orchestrator. Unlike power skills, `skills-assist` does **not** have `disable-model-invocation` set, so the LLM can invoke it autonomously to consult the skills authoring expert without requiring an explicit `/skills-assist` command from the user.

The `image-vision` skill is a simpler reference skill that loads inline (without forking) and activates in the agent's existing context window.

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
    source: git+https://github.com/microsoft/amplifier-bundle-skills@main#subdirectory=modules/tool-skills
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
├── modules/
│   └── tool-skills/              # tool-skills module (maintained here; standalone repo deprecated)
│       ├── pyproject.toml
│       ├── amplifier_module_tool_skills/
│       └── tests/
└── skills/
    ├── image-vision/             # LLM-based image analysis
    │   ├── SKILL.md
    │   └── ...
    ├── code-review/              # Parallel code review (power skill)
    │   └── SKILL.md
    ├── mass-change/              # Parallel work orchestration (power skill)
    │   └── SKILL.md
    ├── session-debug/            # Session diagnostics (power skill)
    │   └── SKILL.md
    └── skills-assist/            # Skills authoring expert (expert skill)
        ├── SKILL.md
        ├── authoring-guide.md
        ├── spec-reference.md
        ├── compatibility-matrix.md
        └── skills-vs-agents.md
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

These features are implemented by the tool-skills module at `modules/tool-skills/`. See the [README in that directory](modules/tool-skills/README.md) for full format documentation. Power skills can also be authored and validated using the `/skills-assist` expert skill.

## CLI Integration

Power skills register as slash commands and are available directly from the Amplifier CLI:

- `/code-review` — Run parallel code review on recent changes
- `/mass-change` — Decompose and execute a large change in parallel
- `/session-debug` — Diagnose session issues
- `/skills-assist` — Consult the skills authoring expert for help creating skills, spec compatibility questions, and skills-vs-agents guidance

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
