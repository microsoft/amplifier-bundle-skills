"""DELIBERATE FAILURE — scratch-branch only, never merged.

Companion to tests/test_ci_red_proof_DELETEME.py, for the module suite. Expect
the modules/tool-skills job to report "315 passed, 1 failed".
"""


def test_ci_can_go_red_module_suite():
    assert 1 == 2, "deliberate failure: proving the tool-skills suite really executes in CI"
