---
name: adapt-skill
description: >
  Adapt a skill written for another AI coding assistant (Claude Code, Cursor,
  etc.) into a properly structured Amplifier SKILL.md file. Reads the source
  skill, identifies platform-specific conventions, researches the source
  platform if needed, and produces an Amplifier-native skill conforming to
  the Agent Skills specification with Amplifier extensions.
  Use when the user wants to adapt a skill, port a skill, convert a skill
  to amplifier, translate a skill, or has a SKILL.md from another platform
  they want to bring into Amplifier.
user-invocable: true
allowed-tools:
  - read_file
  - write_file
  - glob
  - grep
  - bash
  - delegate
model_role: general
---

# Adapt Skill

Adapt a skill from another AI coding assistant into a properly structured
Amplifier SKILL.md. The output must conform to the Agent Skills specification
with Amplifier extensions and be immediately usable via `/skill-name`.

## Inputs

- `$ARGUMENTS`: (Optional) Path to the source skill file or description of
  what to adapt.

## Steps

### 1. Consult Skills-Assist

Before writing any skill content, load the authoritative skills reference:

```
load_skill("skills-assist")
```

Ask skills-assist about:
- Current frontmatter field reference and best practices
- Fork vs inline decision criteria
- Step annotation conventions
- Testing patterns for the type of skill being created

skills-assist is the source of truth for Amplifier skill conventions. The
examples in this skill are illustrative samples — consult skills-assist
for the complete and up-to-date specification.

**Success criteria**: You have loaded and consulted skills-assist for the
latest skill authoring conventions.

### 2. Explore the Target Bundle

If the user wants to add the skill to a bundle (e.g., `amplifier-bundle-skills`),
delegate to `foundation:explorer` to understand the bundle's conventions,
existing skills, and structure. If saving to a personal or project directory,
skip this step.

**Success criteria**: You understand the target bundle's skill conventions and
can produce a skill that fits in.

### 3. Read and Analyze the Source Skill

Read the source SKILL.md and identify:
- The skill's purpose and core workflow
- Platform-specific tool names (e.g., `Read` vs `read_file`, `AskUserQuestion`
  vs natural conversation, `Bash(mkdir:*)` vs `bash`)
- Platform-specific paths (e.g., `.claude/skills/` vs `.amplifier/skills/`)
- Platform-specific frontmatter fields that need mapping to Amplifier equivalents
  or removal (consult skills-assist for the current Amplifier field reference)
- Conventions that don't exist in Amplifier and need alternative approaches
- The interview or interaction model (does it rely on tools Amplifier doesn't have?)

Present a summary of what needs to change — grouped into natural clusters, not
a wall of text. Let the user confirm the adaptation plan before proceeding.

**Success criteria**: You have a clear mapping of source conventions to
Amplifier equivalents, and the user has confirmed the approach.

### 4. Research Source Platform Conventions (if needed)

If the source skill uses unfamiliar fields or conventions, research the source
platform's official documentation using web search and web_fetch. Compare
the source platform's spec with Amplifier's to identify:
- Fields that map directly (e.g., `name`, `description`, `allowed-tools`)
- Fields that map with translation (e.g., CC's `model` -> Amplifier's `model_role`)
- Fields with no Amplifier equivalent (document the gap, decide whether to drop
  or approximate)

Skip this step if the source conventions are already well understood.

**Success criteria**: You understand the source platform's skill format well
enough to make accurate adaptation decisions.

### 5. Design the Adapted Skill

Walk through these decisions with the user, grouped into natural clusters
(not one question per turn, not everything at once):

**Identity and routing:**
- Suggested name and description (with trigger phrases for the visibility hook —
  the description is the ONLY signal the model sees before deciding to load)
- `model_role` based on the skill's primary cognitive task (consult skills-assist
  for the full set of available roles)

**Execution model:**
- Inline vs forked (`context: fork`). Critical: forked skills CANNOT do
  multi-turn conversation with the user — the sub-agent runs once and returns.
  If the skill needs to interview the user, it must be inline.
- Model-invocable vs user-only (`disable-model-invocation`)
- `allowed-tools` — minimum set needed, translated to Amplifier tool names
  (consult skills-assist for the current tool name reference)

**Save location:**
- This project (`.amplifier/skills/<name>/SKILL.md`)
- Personal (`~/.amplifier/skills/<name>/SKILL.md`)
- A skills bundle (`amplifier-bundle-skills/skills/<name>/SKILL.md`)

**Step structure:**
- Confirm the adapted steps make sense for Amplifier's tool and agent ecosystem
- Identify any steps that need fundamental reworking (not just tool name swaps)

**Success criteria**: All design decisions confirmed by the user.

### 6. Write the SKILL.md

Write the adapted SKILL.md following Amplifier conventions. Consult skills-assist
for the full set of available frontmatter fields and current conventions.

Key principles (illustrative — consult skills-assist for complete reference):
- Frontmatter uses Amplifier fields (`model_role`, `user-invocable`, `context`,
  `disable-model-invocation`, `allowed-tools`, etc.)
- `description` carries all routing weight (trigger phrases, "Use when...")
- Tool references use Amplifier names (`read_file`, `write_file`, `edit_file`,
  `bash`, `glob`, `grep`, `delegate`, etc.)
- Paths reference Amplifier locations (`.amplifier/skills/`, `~/.amplifier/skills/`)
- Agent delegation uses `delegate` tool, not platform-specific mechanisms
- Success criteria on every step

Present the complete SKILL.md in a code block for review before saving.

**Success criteria**: The user has reviewed and approved the adapted SKILL.md.

### 7. Test the Skill

Before committing, verify the skill works:

1. Save the skill to `.amplifier/skills/<name>/SKILL.md` (immediately
   discoverable, no config changes needed).

2. In the same session, call `load_skill("<name>")` and verify:
   - The skill loads without errors
   - The description is clear enough for routing
   - The body instructions are actionable

3. Spawn a test session via `delegate(agent="self", context_depth="none")`
   that exercises the skill:
   - The test agent should load the skill and follow its instructions against
     a synthesized test input (e.g., a small sample source SKILL.md from the
     original platform)
   - Verify the output contains valid Amplifier frontmatter, correct tool
     names, and proper structure

4. If issues are found, fix the SKILL.md and re-test.

**Success criteria**: The skill loads, the test agent follows its instructions,
and the output conforms to Amplifier conventions.

### 8. Save, Commit, and Push

After testing passes:

1. Move the skill from `.amplifier/skills/<name>/` to the final destination
   (bundle directory, personal skills, or leave in project skills).

2. If contributing to a bundle, commit and push via `foundation:git-ops`.

3. Tell the user:
   - Where the skill was saved
   - How to invoke it: `/skill-name [arguments]`
   - That they can edit the SKILL.md directly to refine it

**Success criteria**: The file is at its final destination (and pushed if
targeting a bundle), and the user knows how to use it.
