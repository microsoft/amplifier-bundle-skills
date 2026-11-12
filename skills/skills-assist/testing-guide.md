# Skills Testing Guide

Use separate evidence for package validity, discovery, execution, routing, and
host presentation. Passing one layer does not establish the others. The
[Agent Skills evaluation guide](https://agentskills.io/skill-creation/evaluating-skills)
describes controlled comparisons; the
[description guide](https://agentskills.io/skill-creation/optimizing-descriptions)
focuses on activation.

## Package checks

Check names, descriptions, environment requirements, relative resource closure,
and licensing before loading executable content. The upstream `skills-ref`
validator accepts the standard fields only; Amplifier extension fields need
separate validation. If validating a standard-field projection, label it as such
and retain the original file for actual loader tests. A passing projection is
not a passing unmodified package. Never strip extension fields from production
skills just to make a standard-only checker green.

Test configured discovery with an unrelated working directory, workspace/user
name collisions, and the composed bundle's namespace resolver. Discovery must
not run scripts. Validate script interfaces with `--help`, missing dependencies,
invalid input, and retry/collision cases appropriate to their effects.

## Testing Skills Locally Before Committing

### Quick Validation

1. Confirm that the destination belongs to an already-selected skill source.
   Follow the host's file-write permissions and preserve same-name local work.
   A directory's existence alone does not make it a configured source.
2. Check catalog collisions before refreshing: newly source-discovered names can
   shadow same-name runtime-overlay skills. After the authorized write succeeds
   and collisions are resolved, refresh that source in the active session:
   `load_skill(source="<selected-source-directory>")`. Use the source-only call;
   it discovers metadata without invoking installed skills. This additive merge
   preserves existing source-discovered entries; it does not refresh cached
   metadata or remove entries.
3. For each installed name, call `load_skill(info="<name>")` and check the winning
   `path`. Inspect its `SKILL.md` and resources with file reads, and verify the
   next agent-visible catalog contains the name. A collision may keep an existing
   winner; do not report the new installation as selected when another path wins.
4. Load an inspected inline content skill with `load_skill(skill_name="<name>")`
   only when requested; verify the full content and `skill_directory`.
   Loading a `context: fork` skill starts execution, so use metadata/catalog
   checks instead for installation verification.
5. Check a fresh session with the same selected sources. It should discover the
   installed names without manual registration. The source-only call above does
   not persist source configuration or grant file-write access.

### Behavioral Testing with Self-Delegation

Use `delegate(agent="self")` to spawn a test session that exercises the skill.
The child session inherits all tools including `load_skill`.
These are separate, authorized execution tests with bounded fixtures, not
required steps for confirming an installation.

**For inline skills — test behavioral influence:**

```
delegate(
  agent="self",
  instruction="""
  You are testing a newly created Amplifier skill.

  Step 1: load_skill("<name>")
  Step 2: Follow the skill's instructions using this test input:
          [describe a realistic scenario]
  Step 3: Report what you did and whether the skill's guidance was
          clear and actionable.
  """,
  context_depth="none"
)
```

**For forked skills — test full lifecycle:**

```
delegate(
  agent="self",
  instruction="""
  You are testing a forked skill's end-to-end lifecycle.

  Step 1: load_skill("<name>") — this should trigger fork execution
  Step 2: Report the result: did it execute? What was returned?
          Was the output useful?
  """,
  context_depth="none"
)
```

### What to Check

| Check | How |
|-------|-----|
| Inline content loads when requested | `load_skill(skill_name=...)` returns full content, no error |
| Discovery selects the intended file | Check `load_skill(info=...)` path and inspect frontmatter without invocation |
| Description is routing-effective | Read the visibility hook output — does it give the model enough to route? |
| Body instructions are actionable | The test agent should be able to follow them |
| `$ARGUMENTS` substitution works | Test with and without arguments |
| Fork execution works | For fork skills, verify spawn and result return |
| Companion files accessible | `read_file(skill_directory + "/file.md")` works |

### Testing Workflow

1. Write the inspected skill to the authorized, selected destination
2. Follow Quick Validation above for discovery and any requested inline load
3. If execution testing is authorized, use bounded fixtures to verify behavior
4. If issues found, fix and re-test
5. If moving to a different final destination, repeat discovery/path checks there
6. Commit and push

## Execution cases and receipts

For each migrated skill, define a small realistic task, fixture inputs, and
observable expectations. Run it in a fresh session with the actual skill loader
and available tools. Keep the development conversation out of the test context.
Save generated outputs outside the installed package. Record:

- Skill and source revision; host, provider/model, and mounted tools.
- Input case, whether the skill was actually loaded, and tool failures.
- Output assertions with evidence, elapsed time, and usage when available.
- Separate statuses for execution, rendering, visual inspection, and adapters.

Read back generated files and calculate expected results independently. Check
edits preserve originals. For UI artifacts, use the consuming host's real
rendering and interaction path. Missing image/Excel/cloud adapters should produce
a truthful unavailable result; that verifies handling, not the adapter itself.
Store credentials and raw private session data outside the repository.

## Routing and quality comparisons

Explicitly asking for a skill tests its execution but not natural discovery.
Test ordinary prompts with the full catalog, including relevant requests and
near misses that share words but belong to another skill. Observe actual loads,
not the model's statement that it would use a skill. Repeat cases when estimating
activation rates; a single smoke test is not a reliability measurement.

When claiming improved quality or efficiency, compare the same task with the
previous skill version or without the skill, using separate fresh sessions and
the same provider/tool configuration. Grade outputs against concrete assertions,
review the traces, and retain failures as well as passes. Re-run affected cases
after a correction. Report a small acceptance run as such, not as a benchmark.
