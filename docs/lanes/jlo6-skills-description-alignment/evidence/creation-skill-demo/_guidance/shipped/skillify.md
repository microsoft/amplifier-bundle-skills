---
name: skillify
description: >
  Capture a repeatable process from the current session into a reusable
  Amplifier SKILL.md skill file. Analyzes the conversation, interviews
  the user to confirm structure, and writes a complete skill to disk.
  Use when the user wants to create a skill, save a workflow as a skill,
  turn a process into a reusable skill, or mentions "skillify", "create skill",
  "make a skill", "save as skill", "capture workflow", "turn this into a skill",
  "new skill", or wants to automate a repeatable process they just performed.
user-invocable: true
allowed-tools:
  - read_file
  - write_file
  - glob
  - grep
  - bash
model_role: general
---

# Skillify

Create a well-structured, reusable Amplifier SKILL.md skill file that captures
a repeatable process from the current session so it can be invoked again later
via `/skill-name`. The skill must conform to the Agent Skills specification
with Amplifier extensions.

## Inputs

- `$ARGUMENTS`: (Optional) Description of the process to capture as a skill.

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

### 2. Analyze the Session

Before asking the user anything, analyze the conversation history to identify:
- What repeatable process was performed
- What the inputs and parameters were
- The distinct steps in order
- The success criteria and artifacts for each step (not just "writing code" but
  "an open PR with CI passing")
- Where the user corrected or steered you — these are important design signals
- What tools were used (read_file, write_file, bash, glob, grep, delegate, etc.)
- What agents were delegated to
- What the goals and measurable outcomes were

**Success criteria**: You have a clear mental model of the process, its steps,
inputs, outputs, and success criteria.

### 3. Interview the User

**Output density rule:** Group related decisions into natural clusters — not
one question per turn (tedious) and not everything at once (overwhelming).
Present your analysis first, let the user absorb it, then ask related
questions together. For example, present identity/routing decisions as one
cluster, execution model decisions as another.

Calibrate interview depth to the complexity of the process. A simple 2-step
workflow needs 1-2 rounds. A complex multi-step workflow with parallel tasks
and irreversible actions needs the full treatment.

#### Round 1: High-level confirmation
- Suggest a name and description for the skill based on your analysis.
  Ask the user to confirm or rename.
- Suggest high-level goals and specific success criteria.
- Present the high-level steps you identified as a numbered list.

#### Round 2: Details and arguments
- If the skill needs arguments, suggest them based on what you observed.
- Ask whether this skill should run inline (in the current conversation) or
  forked (`context: fork`) as an isolated subagent. Forked is better for
  self-contained tasks that don't need mid-process user input; inline is
  better when the user wants to steer mid-process.
- Ask where the skill should be saved:
  - **This project** (`.amplifier/skills/<name>/SKILL.md`) — project-specific
  - **Personal** (`~/.amplifier/skills/<name>/SKILL.md`) — follows you across projects
  - **The skills bundle** (`amplifier-bundle-skills/skills/<name>/SKILL.md`) — if
    contributing to the curated collection

#### Round 3: Per-step breakdown (complex processes only)
Skip this round for simple skills with obvious steps. For complex skills:
- What does each step produce that later steps need?
- What proves each step succeeded?
- Should the user confirm before irreversible actions?
- Are any steps independent and could run in parallel?
- How should each step be executed? (direct, delegate to an agent, user action)
- What are hard constraints or preferences?

Pay special attention to places where the user corrected you during the session.
These corrections are the most valuable design signals.

#### Round 4: Final confirmation
- Confirm when this skill should be invoked and review trigger phrases
  for the description field.
- Ask for gotchas or edge cases, if still unclear.

Stop interviewing once you have enough information. Don't over-ask for simple
processes.

**Success criteria**: You have all the information needed to write the SKILL.md
and the user has confirmed the design.

### 4. Write the SKILL.md

Create the skill directory and file at the location the user chose in Round 2.

Use this template as a starting point. Consult skills-assist for the full set of available frontmatter fields and current conventions:

    ---
    name: {{skill-name}}
    description: >
      {{What this skill does. Front-load the key use case. Include trigger
      phrases and "Use when..." guidance — this is what the model sees in the
      skills visibility list to decide whether to auto-invoke.
      Keep under 250 characters for the first sentence; can be longer overall.}}
    user-invocable: true
    allowed-tools:
      {{list of Amplifier tool names observed during the session, e.g.:}}
      {{- read_file}}
      {{- write_file}}
      {{- edit_file}}
      {{- bash}}
      {{- glob}}
      {{- grep}}
      {{- delegate}}
    model_role: {{general | coding | reasoning | critique | writing | fast}}
    {{Only include if forked:}}
    {{context: fork}}
    {{disable-model-invocation: true}}
    ---

    # {{Skill Title}}

    {{Brief statement of what the skill does and its goal. Define concrete
    success artifacts — not just "writing code" but "a passing test suite
    and a committed implementation."}}

    ## Inputs

    - `$ARGUMENTS`: {{Description of expected arguments, or "(Optional) ..."}}

    ## Steps

    ### 1. {{Step Name}}

    {{Specific, actionable instructions. Include commands when appropriate.}}

    **Success criteria**: {{REQUIRED on every step. What proves this step
    is done and we can move on.}}

#### Step annotations (key examples — consult skills-assist for complete conventions):

- **Success criteria** is REQUIRED on every step
- **Execution**: `Direct` (default — omit if direct), `Delegate to [agent]`
  (e.g., "Delegate to foundation:explorer"), or `[human]` (user does it)
- **Artifacts**: Data this step produces that later steps need (PR number,
  commit SHA, file path). Only include if later steps depend on it.
- **Human checkpoint**: Pause and ask before irreversible actions (merging,
  deploying, sending messages, destructive operations)
- **Rules**: Hard constraints. User corrections during the original session
  are especially useful here.

#### Structural conventions:

- Steps that can run concurrently use sub-numbers: 3a, 3b
- Steps requiring the user to act get `[human]` in the title
- Keep simple skills simple — a 2-step skill doesn't need annotations
  on every step

#### Frontmatter rules (key examples — consult skills-assist for complete reference):

- `description` must carry all routing weight — trigger phrases, "Use when..."
  guidance, and example user messages belong here since this is what the
  visibility hook shows to the model
- `allowed-tools` should be the minimum set needed
- `context: fork` only for self-contained skills that don't need user steering
- If forked, usually pair with `disable-model-invocation: true`
- `model_role` should match the skill's primary cognitive task
- `user-invocable: true` registers the skill as a `/name` slash command
- Names must be kebab-case, max 64 characters

**Success criteria**: The complete SKILL.md content has been drafted.

### 5. Test the Skill

Before committing, verify the skill works:

1. Save the skill to `.amplifier/skills/<name>/SKILL.md` (immediately
   discoverable, no config changes needed).

2. In the same session, call `load_skill("<name>")` and verify:
   - The skill loads without errors
   - The description is clear enough for routing
   - The body instructions are actionable

3. Optionally, spawn a test session via `delegate(agent="self",
   context_depth="none")` that loads the skill and follows its
   instructions against a synthesized test input.

4. If issues are found, fix and re-test.

**Success criteria**: The skill loads correctly and its instructions are
actionable.

### 6. Review and Save

Before writing the file, present the complete SKILL.md content in a yaml code
block so the user can review it with proper syntax highlighting.

Ask the user: "Does this look good to save?"

After confirmation:

1. Create the skill directory:
   ```
   mkdir -p <chosen-path>/<skill-name>
   ```

2. Write the SKILL.md file to `<chosen-path>/<skill-name>/SKILL.md`

3. If the skill references companion files (templates, examples, scripts),
   create those as well.

4. Tell the user:
   - Where the skill was saved
   - How to invoke it: `/skill-name [arguments]`
   - That they can edit the SKILL.md directly to refine it
   - If saved to a project or personal directory, the skill will be
     auto-discovered on next session start

**Success criteria**: The file is written to disk and the user knows how to
use it.
