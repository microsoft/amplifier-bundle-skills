# Skills Testing Guide

## Testing Skills Locally Before Committing

### Quick Validation

1. Save the skill to `.amplifier/skills/<name>/SKILL.md` (immediately discoverable,
   no config changes needed)
2. In the same session: `load_skill(skill_name="<name>")`
3. Verify: content loads correctly, `skill_directory` path is correct, frontmatter
   fields parsed as expected

### Behavioral Testing with Self-Delegation

Use `delegate(agent="self")` to spawn a test session that exercises the skill.
The child session inherits all tools including `load_skill`.

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
| Skill loads without errors | `load_skill()` returns content, no error |
| Frontmatter parsed correctly | Check `skill_name`, `skill_directory` in result |
| Description is routing-effective | Read the visibility hook output — does it give the model enough to route? |
| Body instructions are actionable | The test agent should be able to follow them |
| `$ARGUMENTS` substitution works | Test with and without arguments |
| Fork execution works | For fork skills, verify spawn and result return |
| Companion files accessible | `read_file(skill_directory + "/file.md")` works |

### Testing Workflow

1. Write skill to `.amplifier/skills/<name>/SKILL.md`
2. `load_skill()` — verify it loads
3. Spawn test agent — verify behavioral compliance
4. If issues found, fix and re-test
5. Move to final destination (bundle, personal, project)
6. Commit and push
