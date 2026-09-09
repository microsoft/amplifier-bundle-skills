import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

MODULE_PATH = (
    Path(__file__).parents[1]
    / "skills"
    / "second-opinion"
    / "scripts"
    / "resolve_provider.py"
)
SPEC = importlib.util.spec_from_file_location(
    "second_opinion_resolve_provider", MODULE_PATH
)
resolver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolver)


EXPECTED_RESOLVER_SHA256 = (
    "b0919a1b609502812f2ec580b1606b0d0861142b075280269404db60c40deede"
)


def item(
    name="reviewer-a",
    *,
    enabled=True,
    provider_type="openai",
    model="test-model-a",
    scope="project",
):
    return {
        "name": name,
        "enabled": enabled,
        "behaviors": ["project"],
        "config_summary": {
            "type": provider_type,
            "model": model,
            "priority": "100",
            "scope": scope,
        },
    }

class SecondOpinionResolveProviderTests(unittest.TestCase):
    def test_resolver_bytes_are_unchanged_at_the_renamed_path(self):
        self.assertEqual(
            EXPECTED_RESOLVER_SHA256,
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )

    def resolve(self, items, **kwargs):
        return resolver.resolve_provider(items, **kwargs)

    def error(self, code, items, **kwargs):
        with self.assertRaises(resolver.ResolutionError) as raised:
            self.resolve(items, **kwargs)
        self.assertEqual(code, raised.exception.code)

    def test_exact_id_uses_configured_default(self):
        result = self.resolve([item()], config_id="reviewer-a")
        self.assertEqual("reviewer-a", result["provider_id"])
        self.assertEqual("test-model-a", result["model"])
        self.assertEqual("test-model-a", result["configured_default_model"])
        self.assertTrue(result["settings_checked"])
        self.assertFalse(result["mounted_checked"])
        self.assertFalse(result["execution_verified"])

    def test_id_preserves_instance_and_allows_model_override(self):
        result = self.resolve([item()], config_id="reviewer-a", model="test-model-b")
        self.assertEqual("reviewer-a", result["provider_id"])
        self.assertEqual("test-model-b", result["model"])

    def test_scope_and_default_come_from_selected_provider_list_entry(self):
        for scope in ("global", "project"):
            for selected_model in ("test-model-a", "test-model-b"):
                with self.subTest(scope=scope, selected_model=selected_model):
                    provider = item(scope=scope)
                    # Runtime routing fields are not provider-list settings.
                    provider["scope"] = "conversation"
                    result = self.resolve(
                        [provider], config_id="reviewer-a", model=selected_model
                    )
                    self.assertEqual(scope, result["config_scope"])
                    self.assertEqual("test-model-a", result["configured_default_model"])
                    self.assertEqual(selected_model, result["model"])
                    self.assertFalse(result["execution_verified"])

    def test_normalizes_one_star_prefix(self):
        result = self.resolve([item("★ reviewer-a")], config_id="reviewer-a")
        self.assertEqual("reviewer-a", result["provider_id"])

    def test_unknown_disabled_and_duplicate_ids_fail(self):
        self.error("unknown_id", [item()], config_id="missing")
        self.error("disabled_id", [item(enabled=False)], config_id="reviewer-a")
        self.error("duplicate_id", [item(), item("★ reviewer-a")], config_id="reviewer-a")

    def test_family_prefers_unique_matching_default(self):
        result = self.resolve(
            [item("reviewer-a"), item("reviewer-b", model="test-model-b")],
            provider="openai",
            model="test-model-b",
        )
        self.assertEqual("reviewer-b", result["provider_id"])

    def test_family_ambiguity_and_sole_override(self):
        self.error(
            "ambiguous_provider",
            [item("reviewer-a"), item("reviewer-b")],
            provider="openai",
            model="test-model-a",
        )
        self.error(
            "ambiguous_provider",
            [item("reviewer-a"), item("reviewer-b", model="test-model-b")],
            provider="openai",
            model="test-model-c",
        )
        result = self.resolve([item()], provider="openai", model="test-model-b")
        self.assertEqual("reviewer-a", result["provider_id"])
        self.assertEqual("test-model-a", result["configured_default_model"])

    def test_no_default_can_use_explicit_model_only(self):
        no_default = item(model=None)
        result = self.resolve([no_default], config_id="reviewer-a", model="test-model-b")
        self.assertIsNone(result["configured_default_model"])
        self.assertEqual("test-model-b", result["model"])
        self.error("missing_model", [no_default], config_id="reviewer-a")

    def test_dash_default_is_missing_but_explicit_override_is_valid(self):
        no_default = item(model="-")
        result = self.resolve([no_default], provider="openai", model="test-model-b")
        self.assertIsNone(result["configured_default_model"])
        self.assertEqual("test-model-b", result["model"])
        self.error("missing_model", [no_default], config_id="reviewer-a")
        self.error("invalid_model", [item()], config_id="reviewer-a", model="-")

    def test_malformed_schema_and_invalid_models_fail(self):
        malformed = item()
        malformed["config_summary"]["priority"] = 100
        self.error("malformed_schema", [malformed], config_id="reviewer-a")
        self.error("malformed_schema", ["not an entry"], config_id="reviewer-a")
        self.error("malformed_schema", [item(model=100)], config_id="reviewer-a")
        malformed = item()
        malformed["behaviors"] = "project"
        self.error("malformed_schema", [malformed], config_id="reviewer-a")
        malformed = item()
        del malformed["config_summary"]["model"]
        self.error("malformed_schema", [malformed], config_id="reviewer-a")
        for model in (" ", "test-*", "<model>", "bad model", "bad\tmodel", "bad\nmodel"):
            self.error("invalid_model", [item()], config_id="reviewer-a", model=model)
        for model in (" ", "test-*"):
            self.error("malformed_schema", [item(model=model)], config_id="reviewer-a")
        self.error("missing_model", [item()], provider="openai")
        self.error("unknown_provider", [item()], provider="anthropic", model="test-model-a")
        self.error(
            "duplicate_id",
            [item(), item("★ reviewer-a", model="test-model-b")],
            provider="openai",
            model="test-model-b",
        )


class ResolveReviewersTests(unittest.TestCase):
    def resolve(self, items, reviewers, **kwargs):
        return resolver.resolve_reviewers(items, reviewers, **kwargs)

    def error(self, code, items, reviewers, **kwargs):
        with self.assertRaises(resolver.ResolutionError) as raised:
            self.resolve(items, reviewers, **kwargs)
        self.assertEqual(code, raised.exception.code)

    def test_mixed_id_and_provider_selectors_preserve_input_order(self):
        result = self.resolve(
            [item("reviewer-a"), item("reviewer-b", provider_type="anthropic", model="b")],
            [{"provider": "anthropic", "model": "override-b"}, {"id": "reviewer-a"}],
        )
        self.assertTrue(result["ok"])
        self.assertEqual(10, result["concurrency"])
        self.assertEqual(2, result["resolved_count"])
        self.assertEqual([0, 1], [row["index"] for row in result["reviewers"]])
        self.assertEqual(
            [("reviewer-b", "override-b"), ("reviewer-a", "test-model-a")],
            [(row["provider_id"], row["model"]) for row in result["reviewers"]],
        )

    def test_concurrency_accepts_positive_integers_without_a_cap(self):
        reviewers = [{"id": "reviewer-a"} for _ in range(26)]
        result = self.resolve([item()], reviewers, concurrency=25)
        self.assertEqual(25, result["concurrency"])
        self.assertEqual(1, result["resolved_count"])
        self.assertEqual("duplicate_reviewer", result["reviewers"][1]["code"])
        self.assertEqual(list(range(26)), [row["index"] for row in result["reviewers"]])
        self.assertEqual(1, self.resolve([item()], [{"id": "reviewer-a"}], concurrency=1)["concurrency"])

    def test_invalid_concurrency_and_global_batch_inputs_fail(self):
        for concurrency in (True, 0, -1, 1.5, "1"):
            with self.subTest(concurrency=concurrency):
                self.error("invalid_concurrency", [item()], [{"id": "reviewer-a"}], concurrency=concurrency)
        self.error("invalid_reviewers", [item()], {"id": "reviewer-a"})
        self.error("empty_reviewers", [item()], [])
        self.error("malformed_schema", "not a list", [{"id": "reviewer-a"}])
        self.error("duplicate_id", [item(), item("★ reviewer-a")], [{"id": "reviewer-a"}])

    def test_invalid_members_are_rows_and_do_not_prevent_valid_resolution(self):
        secret = "secret-selector-value"
        reviewers = [
            None,
            {},
            {"id": "reviewer-a", "provider": "openai"},
            {"id": "reviewer-a", "unexpected": secret},
            {"id": ""},
            {"id": 1},
            {"id": "reviewer-a", "model": "bad model"},
            {"id": "reviewer-a", "model": None},
            {"provider": "openai"},
            {"provider": 1, "model": "test-model-a"},
            {"provider": "openai", "model": "test-*"},
            {"id": "reviewer-a"},
        ]
        result = self.resolve([item()], reviewers, concurrency=1)
        self.assertFalse(result["ok"])
        self.assertEqual(1, result["resolved_count"])
        self.assertEqual(list(range(len(reviewers))), [row["index"] for row in result["reviewers"]])
        self.assertEqual(
            [
                "invalid_reviewer",
                "invalid_reviewer",
                "invalid_reviewer",
                "invalid_reviewer",
                "invalid_selector",
                "invalid_selector",
                "invalid_model",
                "invalid_model",
                "missing_model",
                "invalid_selector",
                "invalid_model",
                None,
            ],
            [row.get("code") for row in result["reviewers"]],
        )
        self.assertNotIn(secret, json.dumps(result))

    def test_duplicate_resolution_is_reported_per_later_row(self):
        result = self.resolve(
            [item("reviewer-a")],
            [{"id": "reviewer-a"}, {"provider": "openai", "model": "test-model-a"}],
        )
        self.assertFalse(result["ok"])
        self.assertEqual(1, result["resolved_count"])
        duplicate = result["reviewers"][1]
        self.assertEqual((False, 1, "duplicate_reviewer"), (duplicate["ok"], duplicate["index"], duplicate["code"]))


class CliTests(unittest.TestCase):
    def invoke(self, argv, run_side_effect=None, stdout='[{"name":"reviewer-a","enabled":true,"behaviors":["project"],"config_summary":{"type":"openai","model":"test-model-a","priority":"100","scope":"project"}}]', returncode=0):
        completed = subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="secret stderr")
        with patch.object(
            resolver.subprocess,
            "run",
            side_effect=run_side_effect,
            return_value=completed,
        ) as run:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = resolver.main(argv)
        return status, json.loads(output.getvalue()), run

    def test_parser_conflict_and_output_is_safe_json(self):
        status, result, run = self.invoke(["--id", "reviewer-a", "--provider", "openai"])
        self.assertEqual(1, status)
        self.assertEqual("usage_error", result["code"])
        run.assert_not_called()

    def test_subprocess_errors_do_not_echo_output(self):
        status, result, _ = self.invoke(["--id", "reviewer-a"], returncode=2)
        self.assertEqual((1, "cli_failed"), (status, result["code"]))
        self.assertNotIn("secret", json.dumps(result))
        status, result, _ = self.invoke(["--id", "reviewer-a"], stdout="not json")
        self.assertEqual((1, "invalid_json"), (status, result["code"]))
        status, result, _ = self.invoke(
            ["--id", "reviewer-a"], run_side_effect=subprocess.TimeoutExpired([], 30)
        )
        self.assertEqual((1, "cli_timeout"), (status, result["code"]))
        status, result, _ = self.invoke(
            ["--id", "reviewer-a"], run_side_effect=FileNotFoundError()
        )
        self.assertEqual((1, "cli_missing"), (status, result["code"]))
        status, result, _ = self.invoke(
            ["--id", "reviewer-a"],
            run_side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "secret"),
        )
        self.assertEqual((1, "cli_failed"), (status, result["code"]))
        self.assertNotIn("secret", json.dumps(result))

    def test_cli_forwards_cwd_and_uses_no_fallback(self):
        status, result, run = self.invoke(
            ["--id", "reviewer-a", "--cwd", "/safe/cwd"]
        )
        self.assertEqual(0, status)
        self.assertTrue(result["ok"])
        self.assertEqual(
            ["amplifier", "provider", "list", "--format", "json"], run.call_args.args[0]
        )
        self.assertEqual("/safe/cwd", run.call_args.kwargs["cwd"])
        self.assertEqual(30, run.call_args.kwargs["timeout"])
        self.assertEqual(1, run.call_count)

        status, result, run = self.invoke(["--id", "reviewer-a"])
        self.assertEqual(0, status)
        self.assertTrue(result["ok"])
        self.assertEqual(str(Path.cwd()), run.call_args.kwargs["cwd"])

    def test_batch_cli_exit_codes_and_loads_provider_list_once(self):
        status, result, run = self.invoke(
            [
                "--reviewers-json",
                '[{"id":"reviewer-a"},{"id":"missing"}]',
                "--concurrency",
                "25",
                "--cwd",
                "/safe/cwd",
            ]
        )
        self.assertEqual(1, status)
        self.assertEqual((25, 1), (result["concurrency"], result["resolved_count"]))
        self.assertEqual(1, run.call_count)
        self.assertEqual("/safe/cwd", run.call_args.kwargs["cwd"])

        status, result, run = self.invoke(
            ["--reviewers-json", '[{"id":"missing"}]']
        )
        self.assertEqual((2, 0), (status, result["resolved_count"]))
        self.assertEqual(1, run.call_count)

        status, result, run = self.invoke(
            ["--reviewers-json", '[{"id":"reviewer-a"}]', "--concurrency", "0"]
        )
        self.assertEqual((2, "invalid_concurrency"), (status, result["code"]))
        run.assert_not_called()

    def test_batch_cli_invalid_concurrency_and_cli_failures_are_safe(self):
        for value in ("-1", "1.5", "not-an-integer"):
            with self.subTest(value=value):
                status, result, run = self.invoke(
                    ["--reviewers-json", '[{"id":"reviewer-a"}]', "--concurrency", value]
                )
                self.assertEqual(2, status)
                self.assertNotIn("reviewer-a", json.dumps(result))
                run.assert_not_called()

        status, result, run = self.invoke(
            ["--reviewers-json", '[{"id":"reviewer-a"}]'],
            run_side_effect=subprocess.TimeoutExpired([], 30),
        )
        self.assertEqual((2, "cli_timeout"), (status, result["code"]))
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(1, run.call_count)

    def test_batch_cli_rejects_unsafe_or_conflicting_input_before_loading(self):
        secret = "secret-reviewer-value"
        for argv in (
            ["--reviewers-json", "not json"],
            ["--reviewers-json", "[]"],
            ["--reviewers-json", '[{"id":"reviewer-a"}]', "--model", "model-a"],
            ["--reviewers-json", '[{"id":"reviewer-a"}]', "--id", "reviewer-a"],
            ["--id", "reviewer-a", "--concurrency", "1"],
        ):
            with self.subTest(argv=argv):
                status, result, run = self.invoke(argv)
                self.assertEqual(2 if "--reviewers-json" in argv else 1, status)
                self.assertNotIn(secret, json.dumps(result))
                run.assert_not_called()

        status, result, run = self.invoke(
            ["--reviewers-json", '[{"id":"secret-reviewer-value","extra":"x"}]']
        )
        self.assertEqual(
            (2, "invalid_reviewer"), (status, result["reviewers"][0]["code"])
        )
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(1, run.call_count)

    def test_batch_global_provider_failure_is_exit_two(self):
        status, result, run = self.invoke(
            ["--reviewers-json", '[{"id":"reviewer-a"}]'],
            stdout='[{"name":"secret-provider"}]',
        )
        self.assertEqual((2, "malformed_schema"), (status, result["code"]))
        self.assertNotIn("secret-provider", json.dumps(result))
        self.assertEqual(1, run.call_count)

if __name__ == "__main__":
    unittest.main()