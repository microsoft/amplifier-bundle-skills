---
bundle:
  name: skills
  version: 1.1.0
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
| **goal-batch** | Plan a batch of independent work into isolated lanes, run each as an autonomous /goal session in its own worktree/branch/tmux, and verify and merge the results yourself |
| **image-vision** | LLM-based image analysis across multiple providers (Anthropic, OpenAI, Gemini, Azure) |
| **cli-packaging-patterns** | CLI tool packaging with one-line install (`uv tool install`/`npm install -g`), subcommand dispatch, 3-tier config resolution |
| **config-state-patterns** | Configuration files with defaults merging, atomic state writes, conventional file locations (XDG), safe concurrent access |
| **http-service-patterns** | FastAPI lifecycle, SPA + API reverse proxy, bidirectional WebSocket relay, SSE event streaming |
| **auth-tls-patterns** | Localhost bypass, PAM/password/auto-generate auth cascade, token auth, TLS auto-setup (Tailscale/mkcert/self-signed) |
| **msgraph-integration-patterns** | Probing, building, troubleshooting Microsoft Graph APIs from browser SPAs with MSAL.js; OData quirks, permissions/consent, recordings/transcripts, CSP, retry patterns, MSAL/EasyAuth auth loops |
| **self-managing-tool-patterns** | Doctor diagnostics, PEP 610 install detection, self-update, cross-platform service install (systemd/launchd) |
| **file-ipc-patterns** | Filesystem IPC without a message broker — JSONL event logs, atomic state snapshots, async request/response, SSE from file tail |
| **instance-storage-patterns** | Per-instance isolated directories, file locking with `defaultdict(Lock)`, prepare-once/create-many session factories |
| **container-orchestration-patterns** | Docker container lifecycle with safety limits, watchdog monitoring, orphan recovery, sidecar provisioning |
| **plugin-discovery-patterns** | Runtime plugin discovery via Python entry points, file-based registry, provider abstractions, schema validation |
| **react-microfrontend-patterns** | Shared React via import maps, frecency autocomplete, Zustand state with localStorage persistence |

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
