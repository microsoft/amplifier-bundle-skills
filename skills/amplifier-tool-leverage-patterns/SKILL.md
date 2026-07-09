---
name: amplifier-tool-leverage-patterns
description: >
  Use when building an Amplifier-powered workflow or automation tool and
  deciding how to expose it — as standalone .dot attractor pipelines (incl.
  inside the Resolve dot-graph resolver), an importable Python lib, agent-callable
  tool modules, or a CLI. Covers the four leverage levels, the DRY rule that keeps
  logic in ONE home, the judgment for which levels a real consumer actually needs
  (and when adding a level is just ceremony), and the maximally-DRY attractor-only
  specialization where the .dot pipeline is the sole logic home.
---

# Amplifier Tool Leverage Levels

## The Pattern

**Problem:** You've built a workflow/automation tool on Amplifier. Different consumers want to use it different ways — an attractor pipeline wants to compose it, a web app wants to import it, an agent wants to call it as a tool, a human wants a CLI. You don't want four copies of the logic.

**Approach:** Pick ONE home for the logic, then expose up to **four leverage levels** as *thin adapters* over that home. Build only the levels a real consumer demands.

| Level | Surface | Consumer | What it is |
|-------|---------|----------|------------|
| **L1** | `.dot` attractor pipelines | Other pipelines / Resolve | One `.dot` per command + a shared subgraph (folder-shape), run on the loop-pipeline engine (`amplifier-bundle-attractor`) |
| **L2** | Python lib | Other codebases | Each command an importable method; clean public API in `__init__.py` |
| **L3** | Amplifier tool modules | Agents | `bundle.md` + `modules/tool-<name>/` wrapping each command as an agent-callable tool |
| **L4** | CLI | Humans / scripts | Thin click/argparse wrapper over the lib |

## The four levels, concretely

**L1 — Standalone `.dot` attractor pipelines.** One `.dot` per command, plus a shared subgraph factored out via a `folder`-shape node. Runs on the loop-pipeline engine anywhere — **including inside the Amplifier Resolve dot-graph resolver**: register a `<name>.dot` + `<name>.resolver.yaml` in the resolver's `pipelines/` dir. Inside the graph, `parallelogram` nodes shell out to the tool's CLI (deterministic steps); `box` nodes are full LLM agents (synthesis steps). This is the level that lets your tool *compose into larger attractor flows*.

**L2 — Python lib.** Each command is an importable method. Export a deliberate public API from `__init__.py`. This is what lets another codebase embed the tool directly — e.g. a web app importing it rather than shelling out.

**L3 — Amplifier tool modules.** A `bundle.md` plus `modules/tool-<name>/` exposing each command as an agent-callable tool. Obey the `mount()` Iron Law; keep each tool a thin wrapper over the lib (run blocking work via `asyncio.to_thread`). This is what lets an agent call your tool as a tool.

**L4 — CLI.** A thin click/argparse surface over the lib. Almost always worth it — it's the cheapest level and it's what L1's `parallelogram` nodes shell out to.

## The DRY rule (load-bearing)

The logic lives in **ONE place**; every level is a thin adapter over it. Where "one place" is depends on the nature of the work:

- **LLM-logic tools** → the home is the **`.dot` files**. The prompts and graph *are* the logic. L2/L3/L4 orchestrate runs of those graphs.
- **Deterministic tools** (e.g. git plumbing) → the home is the **lib**. The `.dot` files are *thin orchestration that shells out to the CLI/lib*.

Two failure modes to refuse:

1. **Don't re-implement logic in the `.dot`.** If the core is deterministic, the `.dot` calls it — it does not reproduce it.
2. **Don't fold a dependency's private engine into your `.dot`.** Keep dependencies behind their public CLI/subprocess boundary. Low coupling beats a fast path that reaches into someone else's internals.

## Sharing across repos without vendoring

When one leverage-repo builds on another (repo-weaver on wiki-weaver), you'll reuse something across a repo boundary. Split the decision by cost and coupling:

- **Heavy / stateful / LLM engine → keep it behind the public boundary.** Shell the other tool's CLI (L4) or compose its `.dot` as a subgraph (L1). Never import its internals — this is failure mode #2 above.
- **Cheap / structural / deterministic facts (paths, layout constants, schemas) → a direct import beats duplication.** Copied constants drift silently; a single source of truth doesn't. Make the upstream a real dependency and import them — this does NOT violate the DRY rule, it honors it across the repo boundary.

To import across repos without vendoring:

1. **Declare the upstream as a git dependency** — `upstream @ git+https://…@main` (companion repos usually aren't on PyPI). Hatchling needs `[tool.hatch.metadata]  allow-direct-references = true` to build a wheel with a direct-URL dep.
2. **Guard against drift with a contract test** that asserts your expected values equal the upstream's exported constants — CI fails the moment they diverge.
3. **Merge order follows the dependency** — the upstream change lands on `main` first (so `@main` resolves the new symbols), then the downstream flips its pin and merges. Same producer→consumer ordering as any cross-repo change.

Evidence: repo-weaver imports wiki-weaver's `WIKI_DIR` / `_sources` / path-helper constants exactly this way (single source of truth for corpus layout), while keeping the synthesis engine behind the subprocess boundary.

## The judgment: which levels do I actually need?

**Do NOT build all four by default.** Build the level a *real consumer* demands:

| Build... | When a real consumer needs... |
|----------|-------------------------------|
| **L1** | Resolve / attractor composition |
| **L2** | an app that will `import` it |
| **L3** | an agent that will call it as a tool |
| **L4** | almost always (cheapest; L1 shells out to it) |

Building a level "to complete the set" is over-engineering. **Prove each level with a real consumer:** L1 is proven by being *registered and RUN* in the resolver; L2 by an actual import; L3 by an agent invocation. A level that is never run by its consumer is ceremony — delete it or don't build it yet.

## When this pattern is the WRONG answer

- **A plain library or CLI does the job and nothing composes/embeds/agent-calls it** → just ship L4 (and maybe L2). Don't reach for attractor pipelines or tool modules to "be thorough." See `cli-packaging-patterns`.
- **The tool isn't Amplifier/LLM-powered at all** → the leverage levels add an Amplifier dependency for no gain. Use ordinary packaging.
- **You can't name the consumer for a level** → that's the signal not to build it. Levels follow demand, not symmetry.

## Worked exemplar: repo-weaver

[`repo-weaver`](https://github.com/microsoft/amplifier-app-repo-weaver) demonstrates all four levels, **each proven**:

- **L1** — its `.dot` pipeline ran end-to-end in the Resolve dot-graph resolver inside a DTU.
- **L2** — exports a public API for direct import.
- **L3** — ships `tool-repo-weaver` (3 tools), proven to return real cited output.
- **L4** — its CLI ran across 30 repos.

repo-weaver crosses into `wiki-weaver` at **two deliberately different boundaries**. Its **deterministic git→docs core lives in the lib**; the heavy LLM synthesis engine stays behind `wiki-weaver`'s **CLI/subprocess** boundary (never imported — low coupling). But the cheap, structural **corpus-layout constants** are a **direct Python import** from `wiki-weaver`'s lib (`wiki-weaver @ git+…@main`), so layout has one source of truth instead of duplicated literals — guarded by a contract test that fails if the two drift. See "Sharing across repos without vendoring" above, and its `ARCHITECTURE.md`, for the boundary in detail.

## Future levels (extensions, not part of the core four)

MCP/REST service wrappers and self-hosted web UIs are natural further leverage levels over the same lib. Add them when a consumer needs them — same rule: prove the consumer first.

## Related skills

- **`cli-packaging-patterns`** — how to build L4 (and the L2 packaging) cleanly.
- **`plugin-discovery-patterns`** — entry-point discovery for L3 tool modules and resolver pipelines.
- **`creating-amplifier-modules`** — the `mount()` Iron Law and module structure for L3.
- **`dot-patterns`** / **`dot-syntax`** — authoring the L1 `.dot` graphs (folder-shape subgraphs, `parallelogram` vs `box` nodes).
