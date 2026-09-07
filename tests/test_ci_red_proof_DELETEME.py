"""DELIBERATE FAILURE — scratch-branch only, never merged.

Exists to prove this repo's brand-new CI can actually go RED, and that the red
comes from the TEST job running the real suite rather than from a setup or lint
error (which would prove nothing). Expect the root job to report
"27 passed, 1 failed".
"""


def test_ci_can_go_red_root_suite():
    assert 1 == 2, "deliberate failure: proving the root suite really executes in CI"
