import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).parents[1] / "skills" / "second-opinion" / "scripts"
LIB_SPEC = importlib.util.spec_from_file_location("provider_resolution", SCRIPTS / "provider_resolution.py")
resolution = importlib.util.module_from_spec(LIB_SPEC)
LIB_SPEC.loader.exec_module(resolution)
WRAPPER_SPEC = importlib.util.spec_from_file_location("second_opinion_resolve_provider", SCRIPTS / "resolve_provider.py")
resolver = importlib.util.module_from_spec(WRAPPER_SPEC)
WRAPPER_SPEC.loader.exec_module(resolver)
import provider_discovery as discovery  # noqa: E402 - script-path import bootstrap


def item(name="reviewer-a", *, enabled=True, provider_type="openai", model="test-model-a", priority="100", scope="project"):
    return {"name": name, "enabled": enabled, "behaviors": ["project"], "config_summary": {"type": provider_type, "model": model, "priority": priority, "scope": scope}}


class ResolveProviderTests(unittest.TestCase):
    def test_active_provider_breaks_only_an_equal_priority_endpoint_tie(self):
        providers = [item("other"), item("★ preferred")]
        result = self.resolve(providers, provider="openai")
        self.assertEqual("preferred", result["provider_id"])
        self.assertEqual("active_provider_tiebreak", result["endpoint_selection"])
        self.assertTrue(any("active" in note for note in result["disclosure"]))
        explicit = self.resolve(providers, config_id="other")
        self.assertEqual("other", explicit["provider_id"])
        self.error("ambiguous_provider", [item("one"), item("two")], provider="openai")
        batch = resolution.resolve_reviewers(
            providers,
            [{"provider": "openai"}, {"id": "preferred", "model": "different-model"}],
        )
        self.assertTrue(batch["ok"])
        later = batch["reviewers"][1]
        self.assertEqual("configured_priority", later["endpoint_selection"])
        self.assertFalse(any("active" in note for note in later["disclosure"]))

    def test_shorthand_latest_and_snapshot_versions(self):
        providers = [item(model="unrelated-model")]
        models = {"reviewer-a": [
            "gpt-6-nova", "gpt-6.1-nova", "gpt-6.1-nova-2026-10-02"
        ]}
        for phrase in ("nova", "latest nova", "latest nova 6", "nova gpt 6.1"):
            with self.subTest(phrase=phrase):
                result = resolution.resolve_request(providers, phrase, inventories=models)
                self.assertEqual("gpt-6.1-nova", result["model"])
        requested = "gpt-6.1-nova-2026-10-02"
        result = resolution.resolve_provider(
            providers, provider="openai", model=requested, inventories=models
        )
        self.assertEqual(requested, result["model"])

    def resolve(self, items, **kwargs):
        return resolution.resolve_provider(items, **kwargs)

    def error(self, code, items, **kwargs):
        with self.assertRaises(resolution.ResolutionError) as raised:
            self.resolve(items, **kwargs)
        self.assertEqual(code, raised.exception.code)

    def test_exact_id_uses_configured_default_and_scope(self):
        provider = item(scope="global")
        provider["scope"] = "conversation"
        result = self.resolve([provider], config_id="reviewer-a")
        self.assertEqual(("reviewer-a", "test-model-a", "global"), (result["provider_id"], result["model"], result["config_scope"]))
        self.assertTrue(result["settings_checked"])
        self.assertFalse(result["execution_verified"])

    def test_exact_id_model_uses_known_equivalence_or_disclosed_unverified_override(self):
        inventory = {"reviewer-a": {"models": [{"id": "nova-6-1", "source": "live", "available": True}]}}
        equivalent = self.resolve([item(model="other")], config_id="reviewer-a", model="nova-6.1", inventories=inventory)
        self.assertEqual(("nova-6-1", "model_match", "available"), (equivalent["model"], equivalent["resolution"], equivalent["model_availability"]))
        override = self.resolve([item()], config_id="reviewer-a", model="unlisted-6")
        self.assertEqual(("unlisted-6", "unverified_override", "unverified"), (override["model"], override["resolution"], override["model_availability"]))
        self.assertTrue(override["disclosure"])

    def test_provider_supported_inventory_is_not_live_execution_proof(self):
        inventory = {"reviewer-a": {"models": [{"id": "nova-6", "source": "provider_supported", "availability": "available"}]}}
        result = self.resolve([item(model="other")], provider="openai", model="nova-6", inventories=inventory)
        self.assertEqual(("provider_supported", "unverified"), (result["inventory_source"], result["model_availability"]))

    def test_normalizes_star_prefix_case_and_rejects_unknown_disabled_duplicate(self):
        self.assertEqual("reviewer-a", self.resolve([item("★ reviewer-a")], config_id="REVIEWER-A")["provider_id"])
        self.error("unknown_id", [item()], config_id="missing")
        self.error("disabled_id", [item(enabled=False)], config_id="reviewer-a")
        self.error("duplicate_id", [item(), item("★ reviewer-a")], config_id="reviewer-a")

    def test_provider_only_uses_lowest_unique_priority_default_and_ties_are_ambiguous(self):
        result = self.resolve([item("slow", priority="100"), item("fast", model="test-model-b", priority="5")], provider="openai")
        self.assertEqual(("fast", "test-model-b", "provider_default"), (result["provider_id"], result["model"], result["resolution"]))
        self.error("ambiguous_provider", [item("one", priority="5"), item("two", priority="5")], provider="openai")

    def test_reordered_tokens_shorthand_and_phrase_version_are_deterministic(self):
        inventory = {"reviewer-a": {"models": [{"id": "vendor-nova-6-1", "source": "live", "available": True}]}}
        reordered = self.resolve([item(model="other")], provider="openai", model="6.1-nova-vendor", inventories=inventory)
        phrase = resolution.resolve_request([item(model="other")], "have nova 6.1 review", inventories=inventory)
        self.assertEqual("vendor-nova-6-1", reordered["model"])
        self.assertEqual("vendor-nova-6-1", phrase["model"])
        self.assertEqual("have nova 6.1 review", phrase["requested_model"])

    def test_latest_and_version_fallback_have_no_list_order_dependence(self):
        inventory = {"reviewer-a": {"models": [
            {"id": "review", "source": "provider_supported", "available": True},
            {"id": "review-5", "source": "live", "available": True},
            {"id": "review-7", "source": "live", "available": True},
        ]}}
        latest = resolution.resolve_request([item(model="other")], "latest review", inventories=inventory)
        fallback = self.resolve([item(model="other")], provider="openai", model="review-6", inventories=inventory)
        self.assertEqual("review-7", latest["model"])
        self.assertEqual(("review-7", "family_substitute", "review-6"), (fallback["model"], fallback["resolution"], fallback["substitute_from"]))

    def test_latest_with_explicit_version_stays_in_known_series_or_discloses_fallback(self):
        inventory = {"reviewer-a": {"models": ["nova-5", "nova-6", "nova-7"]}}
        exact_series = resolution.resolve_request([item(model="other")], "latest nova-6", inventories=inventory)
        self.assertEqual(("nova-6", "model_match"), (exact_series["model"], exact_series["resolution"]))
        missing_minor = resolution.resolve_request([item(model="other")], "latest nova-6.1", inventories=inventory)
        self.assertEqual(("nova-6", "family_substitute", "latest nova-6.1"), (missing_minor["model"], missing_minor["resolution"], missing_minor["substitute_from"]))
        self.assertTrue(missing_minor["disclosure"])

    def test_same_endpoint_equal_model_rank_is_ambiguous_and_no_substring_match(self):
        inventory = {"reviewer-a": {"models": ["nova-6.0", "nova-6-0"]}}
        self.error("ambiguous_model", [item(model="other")], provider="openai", model="nova-6", inventories=inventory)
        with self.assertRaises(resolution.ResolutionError) as raised:
            resolution.resolve_request([item()], "disastra", inventories=inventory)
        self.assertEqual("no_match", raised.exception.code)

    def test_unknown_phrase_never_invents_a_model_or_endpoint(self):
        with self.assertRaises(resolution.ResolutionError) as raised:
            resolution.resolve_request([item()], "unconfigured-label")
        self.assertEqual("no_match", raised.exception.code)
        self.error("no_match", [item(), item("two")], provider="openai", model="unlisted-6")

    def test_schema_and_model_validation_contracts(self):
        malformed = item()
        malformed["config_summary"]["priority"] = 100
        self.error("malformed_schema", [malformed], config_id="reviewer-a")
        self.error("malformed_schema", ["not entry"], config_id="reviewer-a")
        malformed = item()
        malformed["behaviors"] = "project"
        self.error("malformed_schema", [malformed], config_id="reviewer-a")
        malformed = item()
        del malformed["config_summary"]["model"]
        self.error("malformed_schema", [malformed], config_id="reviewer-a")
        for model in (" ", "test-*", "<model>", "bad model", "bad\tmodel"):
            self.error("invalid_model", [item()], config_id="reviewer-a", model=model)
        self.error("missing_model", [item(model=None)], config_id="reviewer-a")
        self.error("unknown_provider", [item()], provider="anthropic")


class ResolveReviewersTests(unittest.TestCase):
    def test_mixed_selectors_order_duplicates_and_partial_rows(self):
        items = [item(), item("reviewer-b", provider_type="anthropic", model="b")]
        result = resolution.resolve_reviewers(items, [{"provider": "anthropic", "model": "b"}, {"id": "reviewer-a"}, {"id": "reviewer-a"}], concurrency=25)
        self.assertEqual(25, result["concurrency"])
        self.assertEqual([0, 1, 2], [row["index"] for row in result["reviewers"]])
        self.assertEqual(2, result["resolved_count"])
        self.assertEqual("duplicate_reviewer", result["reviewers"][2]["code"])

    def test_invalid_members_are_rows_and_global_inputs_fail(self):
        result = resolution.resolve_reviewers([item()], [None, {}, {"id": "reviewer-a", "provider": "openai"}, {"id": "reviewer-a"}], concurrency=1)
        self.assertEqual(["invalid_reviewer", "invalid_reviewer", "invalid_reviewer", None], [row.get("code") for row in result["reviewers"]])
        for value in (True, 0, -1, 1.5, "1"):
            with self.assertRaises(resolution.ResolutionError) as raised:
                resolution.resolve_reviewers([item()], [{"id": "reviewer-a"}], concurrency=value)
            self.assertEqual("invalid_concurrency", raised.exception.code)
        for reviewers, code in (({}, "invalid_reviewers"), ([], "empty_reviewers")):
            with self.assertRaises(resolution.ResolutionError) as raised:
                resolution.resolve_reviewers([item()], reviewers)
            self.assertEqual(code, raised.exception.code)


class CliTests(unittest.TestCase):
    def invoke(self, argv, *, stdout=None, returncode=0, side_effect=None):
        providers = [item()]
        completed = subprocess.CompletedProcess([], returncode, stdout=json.dumps(providers) if stdout is None else stdout, stderr="secret stderr")
        with patch.object(discovery.subprocess, "run", side_effect=side_effect, return_value=completed) as run:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = resolver.main(argv)
        return status, json.loads(output.getvalue()), run

    def test_safe_parser_and_subprocess_errors(self):
        status, result, run = self.invoke(["--id", "reviewer-a", "--provider", "openai"])
        self.assertEqual((1, "usage_error"), (status, result["code"]))
        run.assert_not_called()
        for stdout, code in (("not json", "invalid_json"),):
            status, result, _ = self.invoke(["--id", "reviewer-a"], stdout=stdout)
            self.assertEqual((1, code), (status, result["code"]))
        status, result, _ = self.invoke(["--id", "reviewer-a"], side_effect=subprocess.TimeoutExpired([], 8))
        self.assertEqual((1, "cli_timeout"), (status, result["code"]))
        for side_effect, code in ((FileNotFoundError(), "cli_missing"), (UnicodeDecodeError("utf-8", b"\\xff", 0, 1, "secret"), "cli_failed")):
            status, result, _ = self.invoke(["--id", "reviewer-a"], side_effect=side_effect)
            self.assertEqual((1, code), (status, result["code"]))
            self.assertNotIn("secret", json.dumps(result))
        status, result, _ = self.invoke(["--id", "reviewer-a"], returncode=2)
        self.assertEqual((1, "cli_failed"), (status, result["code"]))
        self.assertNotIn("secret", json.dumps(result))

    def test_invalid_batch_and_selector_inputs_do_not_load_cli_or_echo_secret(self):
        for argv, expected in (
            (["--reviewers-json", "not json"], "invalid_reviewers"),
            (["--reviewers-json", "[]"], "empty_reviewers"),
            (["--reviewers-json", '[{"id":"reviewer-a"}]', "--concurrency", "0"], "invalid_concurrency"),
        ):
            status, result, run = self.invoke(argv)
            self.assertEqual(2, status)
            self.assertEqual(expected, result["code"])
            run.assert_not_called()
            self.assertNotIn("reviewer-a", json.dumps(result))
        status, result, run = self.invoke(["--id", "reviewer-a", "--model", "bad model"])
        self.assertEqual((1, "invalid_model"), (status, result["code"]))
        run.assert_not_called()
        status, result, run = self.invoke(["--unrecognized", "secret-selector"])
        self.assertEqual((1, "usage_error"), (status, result["code"]))
        run.assert_not_called()
        self.assertNotIn("secret-selector", json.dumps(result))

    def test_cli_loads_provider_list_once_and_batch_exit_contract(self):
        status, result, run = self.invoke(["--id", "reviewer-a", "--cwd", "/safe/cwd"])
        self.assertEqual(0, status)
        self.assertTrue(result["ok"])
        self.assertEqual(["amplifier", "provider", "list", "--format", "json"], run.call_args.args[0])
        self.assertEqual("/safe/cwd", run.call_args.kwargs["cwd"])
        with patch.object(discovery, "probe_inventory", return_value=([], False)):
            status, result, run = self.invoke(["--reviewers-json", '[{"id":"reviewer-a"},{"id":"missing"}]'])
            self.assertEqual((1, 1), (status, result["resolved_count"]))
            self.assertEqual(1, run.call_count)
            status, result, run = self.invoke(["--reviewers-json", '[{"id":"missing"}]'])
            self.assertEqual((2, 0), (status, result["resolved_count"]))
            self.assertEqual(1, run.call_count)
        status, result, run = self.invoke(["--reviewers-json", '[null,{"provider":1},{"id":"reviewer-a"}]'])
        self.assertEqual((1, 1), (status, result["resolved_count"]))
        self.assertEqual([0, 1, 2], [row["index"] for row in result["reviewers"]])
        self.assertTrue(result["reviewers"][2]["ok"])


if __name__ == "__main__":
    unittest.main()
