---
name: bug-report
description: >-
  Investigate a defect and write an evidence-backed maintainer report.
  USE WHEN asked to file a bug, report an issue, investigate and report, or
  write a defect up for devs. DO NOT USE WHEN only a fix or direct debugging
  is wanted — use the normal debugging workflow.
user-invocable: true
---

# Bug Report

Turn a defect into a report a maintainer can act on without a follow-up
conversation: evidence they can re-run, a root cause named with `file:line`
when established, verification status, and an honest account of what you did
not check. Unknown causes and unverified fixes are useful when labelled honestly.

**Success artifact:** a single `.md` file whose every factual claim traces to
output you actually captured. Filing it anywhere follows the user's intent and
applicable routing guidance (step 6); the local file alone is a complete outcome.

## Inputs

`$ARGUMENTS` — the defect, the repo, or both. If neither is clear, ask what's
broken and which repo owns it before proceeding.

Also resolve the report location and filing destination from the request,
applicable user preferences/memories, workspace/environment guidance, and agent
context. Honor established overrides before choosing defaults; distinguish the
repo containing the defect from the destination receiving the report. Do not
require the user to repeat a location or filing instruction already established.
If applicable instructions genuinely conflict, ask one focused question.

---

## The discipline that makes these reports worth reading

The steps below are scaffolding. This section is the actual content. Apply
judgment — these are failure modes to steer around, not boxes to tick.

**Evidence is perishable — capture before you touch.** Stuck processes, orphaned
windows, open file descriptors, a tmp file mid-write: fixing or even poking at
these destroys the evidence. Snapshot first, diagnose second, fix third.

**A positive control is mandatory, not optional.** Before concluding anything
from an absence, prove the thing you're measuring *can be present*. A pass
condition satisfied by absence is a false positive, not a pass.

> Real example: a test asserted "no orphan process alive after SIGKILL" and
> printed PASS. No orphan had ever been created — the process under test never
> spawned. The harness even printed `cannot test the reap path` two lines
> earlier and reported PASS anyway. If the control didn't fire, the result is
> INCONCLUSIVE. Say so.

**Change exactly one variable.** Bundle in, bundle out. Patch applied, patch
reverted. Everything else held constant, including the harness.

**Verify fixes by running them, never by reading them.** Reproduce → patch →
re-run → confirm the symptom is gone. "The code now looks correct" is not
evidence.

**Read the code's own comments before proposing a fix.** Maintainers often
already rejected the obvious fix for a reason they wrote down.

> Real example: a hook built raw dicts where typed models were declared. The
> obvious fix — use the typed models — was already rejected upstream in a
> docstring, because those models serialize an extra key the API rejects. The
> real bug was a *warning filter* that never matched. Proposing the obvious fix
> would have broken the wire format and burned the maintainer's time.

**Your own tooling is a suspect.** When a measurement looks strange — especially
a constant count, or a value that changes every sample for no reason — check
whether the instrument is producing it.

> Real traps, both of which produced wrong findings before being caught: a
> process query whose filter string matched *the query process itself* (constant
> count of 1, new PID every sample, reads exactly like a respawn loop); and a
> binary not on `PATH` returning empty output that reads identically to "no
> matches found."

**When you're wrong, separate what falls from what stands.** A correction that
retracts everything is as useless as one that retracts nothing. Name the
invalidated claim, name what independently survives, and say why.

**"Not investigated" is a required section.** Analogous code paths you didn't
test, hypotheses you couldn't confirm, platforms you couldn't reach. Label
guesses as guesses — a hypothesis presented as a finding is worse than silence.

---

## 1. Capture live state

Snapshot relevant perishable state *before* touching anything: process, window,
file/socket state, logs, and timestamps as needed. For deterministic failures,
capture the minimal command, inputs, versions, and output instead of a broad
machine inventory. Note the current time so ages can be computed later.

**Rules:**
- Do not fix, kill, or restart anything in this step.
- Preserve relevant raw evidence verbatim in private storage, outside public
  repositories and upload/artifact paths. Summarize and redact for the report.
- With no capture-location preference, use a task-owned private directory and
  verify it is untracked and excluded from uploads. Do not commit raw captures
  or infer privacy solely from a hidden/ignored directory name.

**Artifacts:** private raw captures — the source for traceable excerpts in step 5.

**Success criteria:** enough state captured that the defect could be described
even if it vanished in the next minute.

## 2. Identify the target repo and pin the version

Resolve which repo owns the defect and the exact commit under test. Note the
environment: OS, runtime versions, relevant package versions.

**Rules:**
- Check whether local edits or stale editable installs are shadowing the version
  you think you're testing. Confirm the working tree is clean before attributing
  behavior to upstream code.

**Artifacts:** `repo`, `commit`, `environment` — the report's metadata block.

**Success criteria:** you can state exactly what code produced the behavior.

## 3. Reproduce with a positive control

Build the smallest reproduction that triggers the defect, with a control proving
the mechanism under test actually engaged.

**Rules:**
- If the control doesn't fire, the result is INCONCLUSIVE. Never a pass.
- Isolate to one variable. Re-run enough times to distinguish signal from flake —
  a decisive claim resting on a single trial is thin.

**Artifacts:** `reproduction` — commands and observed output.

**Success criteria:** the defect reproduces and the control fired, or the report
records INCONCLUSIVE with the failed control, blocker, and missing observation.

## 4. Find root cause, then check it against the maintainer's intent

Trace to the specific mechanism and cite `file:line`. Read surrounding comments,
docstrings, and commit messages before forming a fix.

**Rules:**
- If your proposed fix contradicts something the code deliberately does, you have
  found a different bug than you think. Re-diagnose.
- Distinguish "works as designed, design is wrong" from "does not work as
  designed." They need different fixes and different framing.

**Artifacts:** `root_cause`, `proposed_fix`.

**Success criteria:** the mechanism is named precisely enough to find, or root
cause is NOT DETERMINED with hypotheses clearly separated from findings.

## 5. Verify the fix, then write the report

When safe and within scope, apply the proposed fix in an isolated worktree or
test environment at the pinned version, re-run the reproduction, and capture
before/after evidence. Do not patch a live installation merely to complete a
report. If verification is unavailable or unsafe, write an UNVERIFIED proposal
with the blocker and the check needed; if no fix is known, say so.

Use `${SKILL_DIR}/templates/report-template.md` for structure.
Write to the established report path/directory. With no preference, choose a
workspace-appropriate local report file, say where it is, and avoid overwriting
an existing report. Keep raw captures separate from this shareable artifact.

**Rules:**
- If you could not verify the fix, say so explicitly and mark it unverified.
  Never imply verification you don't have.
- Every table and quoted block must be real captured output, not reconstructed
  from memory. Redacted excerpts remain traceable to the private original.
- Redact credentials, tokens, private endpoints, sensitive user/machine data,
  and unrelated PII before writing the shareable report or uploading evidence.
  Mark omissions clearly, e.g. `<redacted: token>` or `<redacted: local path>`;
  never include the sensitive value in a redaction note. Preserve details needed
  to reproduce without identifying the reporting machine. Public GitHub aliases
  and attribution already inherent in issue filing need not be removed.
- Label root cause NOT DETERMINED, reproduction INCONCLUSIVE, and fix UNVERIFIED
  wherever applicable, including the summary. Never invent evidence to satisfy
  a heading. Record any authorized live mitigation and restoration separately.
- Include the method traps you hit — they save the next person the same hours.

**Artifacts:** `report_path` — the finished `.md`.

**Success criteria:** every factual claim traces to captured evidence, and the
"Not investigated" section is populated honestly.

## 6. Decide where it goes

**This is where the skill stops by default.** The `.md` file is the deliverable.
Suggest confirming the destination and title before remote filing when intent
is unclear. This is guidance, not a mandatory extra approval round: a clear
request to file, or applicable standing user/environment/agent instructions,
can already settle that decision. Honor a decline or a report-only request.

Use the established filing destination first, including a separate support
tracker when context directs that route. Do not redirect merely because a
different repo accepts issues. With no routing override, use the defect's repo
as the candidate destination; Issues being enabled alone is not filing intent.

For a GitHub destination, check what the **destination** actually accepts:

```bash
gh repo view <owner>/<repo> --json hasIssuesEnabled,isArchived,isFork,viewerPermission
```

Then apply exactly one branch:

| Repo state | Action |
|---|---|
| Destination accepts issues and is not archived | Follow established filing intent and that destination's intake/duplicate rules; report the URL if filed. Suggest confirmation if intent remains unclear. |
| Destination cannot accept issues | Check applicable guidance for an alternate support route. If none is established, retain the file and explain the available options; do not invent a routing policy. |
| An alternate tracker is established | Use its available, authorized intake workflow; do not assume GitHub commands apply. |
| `gh` or the required intake capability is unavailable, or destination unresolved | Retain the file and explain the limitation; do not guess or claim submission. |

**Human checkpoint:** Never open a pull request unprompted. "Issues are off and
PRs are possible" is a question for the user, never a decision you make for them.
An affirmative answer to a different question does not authorize a PR.

**Rules:**
- Silence is not new authorization, but does not erase existing filing intent
  or applicable standing instructions. Ask only about a genuinely unsettled
  decision, not for ritual repetition of permission already supplied.
- If the user declines, the file remains the deliverable. That is a complete,
  successful outcome — not a failure.
- Keep defect ownership, filing destination, and local report path distinct.
  Reference the affected repo/version in the report even when filed elsewhere.
- Review redactions before remote submission. Do not attach private captures.

**Artifacts:** `issue_url` (only if filed).

**Success criteria:** the report exists in the appropriate local location,
and any submission follows established intent and destination-specific guidance.

## 7. Hand off

Tell the user where the file is, what the headline finding is, whether the fix
was verified, and what remains unchecked. If a gate stopped you, say which one
and what would unblock it.

**Success criteria:** the user knows the outcome and any decision still waiting
on them.
