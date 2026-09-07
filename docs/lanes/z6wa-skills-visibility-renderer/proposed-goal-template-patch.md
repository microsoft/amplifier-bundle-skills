# Proposed goal-template patch — the SYSTEM-STATE / LANE-BAR ambiguity

**Filed by:** lane `z6wa-skills-visibility-renderer`, on resolution.
**Filed under:** the goal's own clause — *"that is a DEFECT IN THIS GOAL, not a task.
Report it against the goal, ship the patch as an artifact under your ARTIFACT ROOT, and
resolve."*
**Cost of not fixing it, observed:** **nine review turns on one lane**, zero measurements
changed, one self-inflicted mislabel (AC2 SPLIT) produced under that pressure and then
corrected. This is the `1ru` churn pattern, and like `1ru` it was produced entirely by the
goal text.

---

## THE DEFECT

A goal states its objective in **two incompatible registers**, and never says which one a
reader should check.

| register | where it appears | what it implies the bar is |
|---|---|---|
| **system state** | the TITLE, and the "WHY THIS IS THE HIGHEST-VALUE TARGET" prose | the span is compressed **in the running system** |
| **lane bar** | OUTCOME branches A/B/C, the LANDING STAGE clause, Procedure 4 | the change is **demonstrated and shipped as a draft PR** |

This goal's title is *"The single largest span in the head, and no file produces it."* Read
as a checkable end state, that is satisfied only by a **merge** — which Procedure 4 forbids
the lane to perform and which requires a **different actor entirely**.

The LANDING STAGE clause already tries to prevent this. **It failed, four times, and the
reasons are structural:**

1. It is **buried inside the OUTCOME section**, below the fold, where a reader checking
   "was the goal met?" against the title never reaches it.
2. It is phrased as an **instruction to the lane** (*"read this before you judge your own
   deliverables"*) rather than as a **definition of the checkable condition**. A reviewer
   or an automated judge does not consider itself the audience.
3. **The title is never corrected.** Whatever the body says, the title is what a judge
   restates when asked "what does this goal require?"
4. Branch **A** names the draft PR in its own text; branch **B** does not. A lane landing in
   B therefore has no in-branch statement that the draft PR is the bar.

**A goal whose title states a condition the lane is forbidden to reach is not a hard goal.
It is an unresolvable one, and no amount of lane effort closes it.**

---

## THE PATCH — five parts, all mechanical

### 1. The title states the LANE's bar, never the system state

```diff
-# Goal: The single largest span in the head, and no file produces it
+# Goal: The single largest span in the head — compress it AT THE RENDERER and ship for landing
```

Rule for the template: **if a title would be satisfied only by a merge, a deploy, or another
actor's action, it is mis-written.** Title the lane's deliverable, not the programme's
outcome.

### 2. A CHECKABLE CONDITION block, first thing in the file, above OUTCOME

```markdown
## CHECKABLE CONDITION (what a reviewer or judge should test)

THIS LANE IS COMPLETE WHEN: <the lane's own bar, in one sentence>.

EXPLICITLY **NOT** THIS LANE'S CONDITION — do not test for these, their absence is
not a defect, and arguing them does not reopen a resolved item:
  - the change being MERGED
  - the change being LIVE in the running system
  - any other repo's half of the same item
  - anything requiring an actor other than this lane
```

That last list is the load-bearing part. A judge cannot infer a negative; it has to be
written down.

### 3. LANDING STAGE becomes a DEFINITION, and is restated in every branch

```diff
-**LANDING STAGE ... — read this before you judge your own deliverables.**
+**LANDING STAGE — DEFINITION OF DONE FOR EVERY DELIVERABLE IN THIS GOAL.**
+This applies to the lane, to any reviewer, and to any automated judge.
```

and in branch B, mirroring branch A's existing parenthetical:

```diff
-**B. RESOLVED AT THE CAP.** The spend authority below could not fund the remaining work, so a
-deliverable is recorded NOT-POSSIBLE-with-reason — and you **still resolve** (branch A's verb)
+**B. RESOLVED AT THE CAP.** The spend authority below could not fund the remaining work, so a
+deliverable is recorded NOT-POSSIBLE-with-reason — and you **still resolve** (branch A's verb,
+and branch A's bar: **the deliverables exist as a draft PR on the module's origin**)
```

### 4. Every headline figure is labelled CURRENT or TARGET

Observed here: the goal says *"measured the `hooks-skills-visibility` block at **5,350
chars**"*. 5,350 is the **replacement text** — `v1_instructions.json` span 11 carries a
`new` field and **no `old` field at all**, and GOAL.md:56 calls them *"lean blocks"*. The
**live** block measures **22,246**.

A reviewer restated this as *"the span remains at 5,350 chars in the actual running
system"* — wrong by ~4x, and it would make an 11,701-char render read as a **regression**
instead of a **−47.4 % cut**.

```diff
-`hooks-skills-visibility` block at **5,350 chars — the single largest span**
+`hooks-skills-visibility` block: **TARGET 5,350 chars** (v1's replacement text; span 11 has
+a `new` field and NO `old` field) against a **CURRENT ~22,000 chars** — the single largest span
```

Rule: **never state a target figure in a sentence whose verb is "measured" or "is".**

### 5. A goal must not carry an acceptance criterion its own authority forbids

This item's AC5 asks for a **wire-head census**. This goal's spend section enumerates the
permitted scope — *"Code/text edits, a test run, a render measurement"* — then states
*"No API measurement is authorised."* A wire-head census **is** an API measurement.
Performing AC5 would have **violated** the goal; omitting it was compliance.

Add to the AUTHORING RULE:

```markdown
Before launch, diff the item's acceptance criteria against this goal's permitted scope.
Any AC the authority forbids must be SPLIT OUT into its own item before launch — never
carried as a criterion the lane is simultaneously required to meet and forbidden to attempt.
```

---

## WHAT THIS WOULD HAVE COST

With parts 1–4 in place, this lane's nine review turns collapse to zero: the title, the
CHECKABLE CONDITION block, and branch B all say the same thing, and the 5,350 figure cannot
be misread as current.

With part 5 in place, AC5 is never in this goal at all — it launches as its own item with
its own authority, which is exactly where it has now had to be filed
(`model_performance-i5n9`).

**Estimated authoring cost of the patch: minutes. Observed cost of its absence: nine review
turns, one mislabel, and one lane that could not be closed by agreement.**
