---
name: amplifier-philosophy
description: Amplifier design philosophy using Linux kernel metaphor. Covers mechanism vs policy, module architecture, event-driven design, and kernel principles. Use when designing new modules or making architectural decisions.
version: 1.0.0
license: MIT
metadata:
  category: architecture
  complexity: medium
---

# Amplifier Philosophy: The Linux Kernel Metaphor

## Core Principle: Mechanism Not Policy

**If two teams might want different behavior, it belongs in a module, not the kernel.**

The kernel provides mechanisms (mount, emit, dispatch). Modules provide policies (what to mount, when to emit, how to handle).

## Architecture Patterns

### Kernel (amplifier-core)

**Keep it minimal and stable:**
- Session management (`session_create`, `mount`, `unmount`)
- Event emission (`emit`)
- Hook registration
- Context access

**Never add to kernel:**
- Provider selection
- Tool routing
- Plan generation
- Default behaviors
- File I/O

### Modules (Everything Else)

**All capabilities as modules:**
- **Providers**: LLM backends (Anthropic, OpenAI, Ollama)
- **Tools**: Capabilities (filesystem, bash, web)
- **Orchestrators**: Execution strategies
- **Context Managers**: State management
- **Hooks**: Lifecycle observers

## Mount Point System

Think of modules as **devices mounted at paths**:

```
/mnt/providers/{name}  - LLM backends
/mnt/tools/{name}      - Agent capabilities
/mnt/hooks/{event}     - Lifecycle observers
/mnt/context           - Conversation state
/mnt/orchestrator      - Execution loop
```

Each mount point has a **stable connector** (Protocol interface).

## Event-Driven Design

**If it's important, emit an event:**

- `session:start`, `session:end`
- `prompt:submit`, `prompt:complete`
- `provider:request`, `provider:response`
- `tool:pre`, `tool:post`
- `context:pre_compact`, `context:post_compact`

**Hooks observe, never interfere:**
- Logging hooks record events
- Approval hooks check permissions
- Cost tracking hooks monitor usage
- Failures in hooks never stop execution

## Module Development Checklist

When creating a new module:

1. ✅ **Implements Protocol only** - No kernel internals
2. ✅ **Emits canonical events** - Observable lifecycle
3. ✅ **Handles own failures** - Never crash kernel
4. ✅ **Configuration via mount()** - No hard-coded defaults
5. ✅ **Entry point registration** - Discoverable

## Decision Framework

### Is This Kernel Work?

Ask: "Would every team use this the exact same way?"

- **Yes** → Might be kernel (rare)
- **No** → Definitely a module

### Extract to Kernel?

Only after:
- Two real implementations exist
- Clear convergence on mechanism
- No opinion baked in

### Prefer Regeneration

- **Don't patch modules** - Regenerate from spec
- **Keep connectors stable** - Module internals can change
- **Update spec, rebuild module** - Not line-by-line edits

## Remember

**Ruthless simplicity.** If two designs solve it, pick the one with fewer moving parts and clearer failure modes.

**Modules compete at edges.** The kernel enables them, doesn't choose between them.

**Observability is mandatory.** If it's not in the logs, it didn't happen.
