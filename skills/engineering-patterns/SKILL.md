---
name: engineering-patterns
description: "Use for tool/service work: CLI packaging, installers, config/state, HTTP, auth/TLS, file IPC, plugins, instance storage, containers, React MFE, Graph, self-update, tool leverage."
---

# Engineering Patterns

Thirteen hard-won pattern guides for building tools and services, behind one
catalog entry. Each guide is a **reference file** — read only the one that
matches the problem in front of you, not the whole set.

## Pick the reference

| If you are... | Read |
|---|---|
| Packaging a CLI — one-line install via `uv`/`npm`, subcommand dispatch, 3-tier config resolution | `references/cli-packaging-patterns.md` |
| Writing a curl-piped installer for a stack that can't use `uv tool install`/`npm publish` | `references/one-line-installer-patterns.md` |
| Persisting config and state — defaults merging, atomic crash-safe writes, XDG locations | `references/config-state-patterns.md` |
| Building an HTTP service — FastAPI lifecycle, background poll loops, SPA + API proxy, WebSocket relay, SSE | `references/http-service-patterns.md` |
| Adding auth or TLS — localhost bypass, token auth with auto-generation, automatic certificates | `references/auth-tls-patterns.md` |
| Making processes talk through the filesystem — JSONL event logs, atomic snapshots, async request/response, SSE from file tailing | `references/file-ipc-patterns.md` |
| Making a system extensible — Python entry points, file-based plugin registry, multi-backend providers, schema validation | `references/plugin-discovery-patterns.md` |
| Managing many concurrent instances/sessions — isolated storage dirs, per-instance locking, prepare-once/create-many factories | `references/instance-storage-patterns.md` |
| Running work in Docker — safety limits, watchdog resource enforcement, orphan recovery, sidecars, reproducible dev stacks | `references/container-orchestration-patterns.md` |
| Building a React frontend that loads independent bundles sharing one React instance — import maps, frecency autocomplete, dynamic forms, Zustand | `references/react-microfrontend-patterns.md` |
| Integrating Microsoft Graph / Teams / MSAL.js — probe methodology, OData quirks, consent sequencing, CSP, retry/pagination, auth-redirect loops | `references/msgraph-integration-patterns.md` |
| Making a CLI manage itself — `doctor` diagnostics, self-update, systemd/launchd service install, post-upgrade verification | `references/self-managing-tool-patterns.md` |
| Deciding how to expose an Amplifier workflow — `.dot` attractor pipeline, Python lib, tool module, or CLI | `references/amplifier-tool-leverage-patterns.md` |

## How to use this

1. Match the problem to a row above.
2. `read_file(skill_directory + "/references/<file>.md")` for that one row.
3. Read a second reference only if the work genuinely spans two topics.

Each reference is the original standalone skill, moved here unchanged — its
frontmatter is retained at the top of the file as provenance. Nothing was
rewritten or dropped in the fold.
