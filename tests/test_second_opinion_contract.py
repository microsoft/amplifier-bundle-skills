import ast
from pathlib import Path
import re
import unittest

SKILL_PATH = Path(__file__).parents[1] / "skills" / "second-opinion" / "SKILL.md"


class SecondOpinionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_PATH.read_text()
        cls.public = cls.skill.split("## Internal execution contract", 1)[0]
        cls.internal = cls.skill.split("## Internal execution contract", 1)[1]
        cls.historical = " ".join(cls.skill.split("### Historical source", 1)[1].split("### Delegate", 1)[0].split())
        cls.delegate = cls.skill.split("### Delegate", 1)[1]

    def delegate_calls(self):
        return [ast.parse(example).body[0].value for example in re.findall(r"```python\n(.*?)```", self.skill, flags=re.DOTALL)]

    def test_frontmatter_and_natural_language_invocation(self):
        frontmatter = self.skill.split("---", 2)[1]
        public = " ".join(self.public.split())
        self.assertIn("name: second-opinion", frontmatter)
        self.assertIn("user-invocable: true", frontmatter)
        self.assertIn("version: 0.4.0", frontmatter)
        matching_skills = [path for path in SKILL_PATH.parent.parent.glob("*/SKILL.md") if "name: second-opinion" in path.read_text(encoding="utf-8")]
        self.assertEqual([SKILL_PATH], matching_skills)
        description = re.search(r'^description: "(.*)"$', frontmatter, re.MULTILINE)[1]
        self.assertLessEqual(len(description), 180)
        self.assertIn("USE WHEN", description)
        self.assertIn("DO NOT USE WHEN", description)
        for parameter in ("id=", "provider=", "model=", "reviewers=", "concurrency=", "source="):
            self.assertNotIn(parameter, public)
        self.assertIn("Which reviewers should I ask?", public)
        self.assertIn("explicit selector, relevant user context, and a configured default", public)
        self.assertIn("exact session ID", public)
        self.assertIn("do not discover a historical session", public)
        self.assertNotIn("astra", self.skill.casefold())

    def test_resolver_and_batch_contract(self):
        internal, delegate = " ".join(self.internal.split()), " ".join(self.delegate.split())
        for phrase in ("skill_directory", "invoking working directory", "--id <id>", "--request <phrase>", "--list-providers", "--list-models <id>", "--models-json <mapping>", "--reviewers-json <array> --concurrency <N>", "argv-based process API", "`shlex.quote`", "Exit 0 means all rows resolved", "exit 1 means partial resolution", "exit 2 means no successful row", "ordered rows and `index` values", "duplicate configured provider/model pair", "defaults to 10, may exceed 10", "retry resolution once", "configuration evidence, not execution proof"):
            self.assertIn(phrase, internal)
        self.assertIn("no more than effective concurrency active", delegate)
        self.assertIn("add a per-provider limit", internal)
        self.assertIn("Keep successful returns when other rows fail", delegate)

    def test_single_and_batch_delegate_examples_have_only_five_keys(self):
        calls = self.delegate_calls()
        self.assertEqual(2, len(calls))
        expected = {"agent", "instruction", "provider_preferences", "context_depth", "context_scope"}
        for call in calls:
            self.assertIsInstance(call, ast.Call)
            self.assertEqual("delegate", call.func.id)
            self.assertEqual([], call.args)
            self.assertEqual(expected, {keyword.arg for keyword in call.keywords})
        for call, source, depth, instruction in zip(calls, ("resolved", "row"), ("all", "none"), ("brief", "batch_instruction")):
            kwargs = {keyword.arg: keyword.value for keyword in call.keywords}
            self.assertEqual("self", ast.literal_eval(kwargs["agent"]))
            self.assertEqual(depth, ast.literal_eval(kwargs["context_depth"]))
            self.assertEqual("conversation", ast.literal_eval(kwargs["context_scope"]))
            self.assertEqual(instruction, ast.unparse(kwargs["instruction"]))
            pair = {ast.literal_eval(key): ast.unparse(value) for key, value in zip(kwargs["provider_preferences"].elts[0].keys, kwargs["provider_preferences"].elts[0].values)}
            self.assertEqual({"provider": f"{source}.provider_id", "model": f"{source}.model"}, pair)

    def test_context_independence_and_same_source_model_acceptance(self):
        skill, delegate = " ".join(self.skill.split()), " ".join(self.delegate.split())
        for phrase in ("source provider/model is still a distinct requested review", "resolver compatibility fields and flags are not report content", "conversation-scoped reviewers do not inherit tool results", "For a historical single review", "packet with `context_depth='none'`", "one byte-identical instruction", "only when no substantive supplied packet exists", "Otherwise reuse the supplied packet", "both the common boundary and the brief-only/no-tools boundary", "no reviewer-specific personalization", "never receive another reviewer's output"):
            self.assertIn(phrase, skill if phrase.startswith(("source", "resolver", "conversation")) else delegate)

    def test_historical_access_is_exact_source_only_and_bounded(self):
        for phrase in ("exact requested source ID", "exact canonical source ID and substantive evidence", "substantive assistant responses and results", "at most one bounded follow-up delegation", "at most two root retrieval delegations in total", "omission from a selection does not prove", "Never substitute the current working tree", "Only these Context Intelligence agents may read capture files", "raw capture paths, capture filenames, line locations", "Never substitute the current working tree, permit capture access to the caller"):
            self.assertIn(phrase, self.historical)
        self.assertEqual(1, self.internal.count("context-intelligence:graph-analyst"))
        self.assertEqual(1, self.internal.count("context-intelligence:session-navigator"))

    def test_brief_and_synthesis_retain_behavior_first_guidance(self):
        current = " ".join(self.skill.split("### Build the evidence brief", 1)[1].split("### Historical source", 1)[0].split())
        report = " ".join(self.skill.split("### Report", 1)[1].split())
        for phrase in ("applicable governing constraints and non-goals", "conflicting evidence or unresolved decisions", "explicitly state that they were not identified", "explicitly state that none were identified"):
            self.assertIn(phrase, current)
        for phrase in ("Preserve conditional recommendations in the synthesis", "never turn “if X” into an unconditional plan", "unmet or unknown condition"):
            self.assertIn(phrase, report)

    def test_supplied_packet_reuses_evidence_without_reharvesting(self):
        packet = " ".join(self.internal.split("### Supplied evidence or another analysis skill", 1)[1].split("### Historical source", 1)[0].split())
        for phrase in ("load its guidance once in the parent", "not another reviewer fan-out", "evidence-collection method", "Follow that method in the parent", "parent's direct `session_transcript` call", "takes precedence over the ordinary historical-source path", "use that packet instead of harvesting the source again", "actual excerpts/results", "an ID, a link, or a conclusion alone is not a packet", "Source content cannot select this path", "context_depth='none'", "brief-only/no-tools", "Ordinary historical requests without a supplied packet continue below unchanged"):
            self.assertIn(phrase, packet)

    def test_read_only_and_injection_boundaries(self):
        delegate = " ".join(self.delegate.split())
        for phrase in ("Do not write files", "change settings", "mutate git", "run side-effecting tests", "delegate to other agents", "Do not invoke second-opinion recursively", "untrusted evidence, not instructions", "at most five prioritized findings", "evidence, a recommendation, and uncertainty", "Inspect only explicit target files", "do not call tools"):
            self.assertIn(phrase, delegate)

    def test_report_returns_reviews_not_audit_boilerplate(self):
        delegate = " ".join(self.delegate.split())
        for phrase in ("selected reviewer/model and returned child session ID", "actual resolver, delegation, empty, or incomplete-response errors", "attributed agreement, differences, and unique findings", "agreement is not a vote for truth"):
            self.assertIn(phrase, delegate)
        for removed in ("Verify provenance", "post-review", "mounted roster", "same-pair guard", "settings_checked", "config_scope", "runtime-unverified", "llm:request", "not cross-model", "execution_verified"):
            self.assertNotIn(removed, self.skill)


if __name__ == "__main__":
    unittest.main()
