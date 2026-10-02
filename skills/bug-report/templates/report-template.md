# <Title stating the defect, not the symptom>

State what is actually wrong, in one line a maintainer can triage from. Not
"overlay problem" — "the disclosure band stays up for the entire session."

**Repo:** `<owner>/<repo>`
**Commit:** `<full sha>` (`<branch>`) — note if this is the commit that fixed a
prior report, so the reader knows what generation they're looking at
**Environment:** OS/kernel, runtime, and the versions that actually matter here
**Severity:** with a one-line justification of why it lands there
**Investigation status:** confirmed / NOT DETERMINED / INCONCLUSIVE, as applicable

The affected repo may differ from the filing destination. Preserve that distinction.

If this is *not* a regression of something previously reported, say so up front.
It saves the maintainer a wrong assumption.

---

## Summary

Three or four sentences. What breaks, what cause is established (or NOT
DETERMINED), and whether a fix is verified or UNVERIFIED. Label an INCONCLUSIVE
reproduction. A reader who stops here should still know whether to act.

---

## Symptom

What the user actually sees, in their terms. Include the verbatim error text or
a description of the visible artifact. If the user's own account is useful
evidence — especially where it contradicts a plausible theory — quote it.

---

## What was actually found

Relevant state captured *before* anything was touched. Quote captured evidence,
redacting credentials, private endpoints, sensitive machine/user details, and
unrelated PII as `<redacted: kind>`. Keep private originals outside the shareable
report; never reveal a sensitive value in the redaction explanation. Ordinary
public GitHub attribution may remain. Omit process-specific tables when irrelevant.

| <thing> | <when> | <age> | <identifier> |
|---|---|---|---|
| | | | |

Trace the relationship between what was observed and what owns it — process to
parent, artifact to producer. State whether owners were alive or dead, because
that distinction usually decides which of two very different bugs this is.

---

## Root cause

Name the mechanism and cite `file:line`. Quote the relevant source, including
its own comments — especially if those comments explain a deliberate choice that
constrains the fix.

If not established, write NOT DETERMINED and separate labelled hypotheses from
observations. State the missing evidence; do not invent a causal explanation.

```
<the actual code>
```

Then explain plainly why that produces the symptom. If it works exactly as
written and the *design* is what's wrong, say that explicitly — it changes what
the fix has to be.

---

## Why this matters more than it looks

Optional. Include when the severity isn't self-evident: a safety property being
eroded, a signal that stops carrying information, a failure that compounds
silently. Skip it when the impact speaks for itself.

---

## Proposed fix

If none is known, say so. A proposed patch is not a verified fix.

```diff
- <before>
+ <after>
```

### Verification status

Show it. Before/after table, or captured output from a real re-run.
Name the isolated test environment and pinned version. Do not imply a live
installation was patched unless it was authorized and actually done.

| | before | after |
|---|---|---|
| <symptom> | <observed> | <observed> |

If it could **not** be verified, say so here in plain terms and mark it
UNVERIFIED. Never imply verification you don't have — an unverified fix that is
labelled as such is useful; one that is not is a trap.

### Recommended beyond the immediate fix

Ranked, with reasoning. Distinguish "must fix" from "worth reconsidering." If
you are arguing against a design decision the maintainer made deliberately, say
that you understand why it exists before saying why it should change.

---

## Reproduction

Numbered, copy-pasteable, no missing context. Someone with the repo and a
terminal should be able to follow it cold.
Include the positive control and its observed result. If it failed or the
defect could not be reproduced, label INCONCLUSIVE and explain the blocker.

```bash
# 1. ...
# 2. ...
```

### Measurement notes for anyone re-running this

Any trap that cost you a wrong answer. This is often the most valuable section
in the whole document — it is knowledge that exists nowhere else, and it stops
the next person burning the same hours. Examples of the shape:

- a query whose filter matched its own process, producing a phantom pattern
- a binary not on `PATH`, whose failure output is indistinguishable from an
  empty result

---

## Not investigated

Required. Never omit, never leave empty.

- Analogous paths not tested (other platforms, sibling modules) and why
- Hypotheses you could not confirm — **labelled explicitly as hypotheses**
- Anything you deliberately left alone, with the reason

A guess presented as a finding costs more than saying nothing.

---

## Local mitigation currently in place

Only if you changed something on the reporting machine. Say exactly what, where
the original is preserved, and whether the change survives an update or reinstall
— a stopgap misread as a fix will cause a confusing bug report later.
