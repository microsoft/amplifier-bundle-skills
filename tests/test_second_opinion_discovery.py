import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner


SCRIPTS = Path(__file__).parents[1] / "skills" / "second-opinion" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inventory = load("model_inventory")
import provider_discovery as discovery  # noqa: E402 - script-path import bootstrap
resolver = load("resolve_provider")


class DiscoveryTests(unittest.TestCase):
    def test_real_app_api_shape_uses_selected_module_and_private_config_in_process(self):
        calls = []

        class Settings:
            def get_provider_overrides(self):
                return [SimpleNamespace(id="configured", module="provider.module", config={"token": "secret"})]

        settings = types.ModuleType("amplifier_app_cli.lib.settings")
        settings.AppSettings = Settings
        loader = types.ModuleType("amplifier_app_cli.provider_loader")

        def get_provider_models(provider_id, config_manager=None, collected_config=None):
            calls.append((provider_id, config_manager, collected_config))
            return [SimpleNamespace(id="review-6")]

        loader.get_provider_models = get_provider_models
        package, lib = types.ModuleType("amplifier_app_cli"), types.ModuleType("amplifier_app_cli.lib")
        paths = types.ModuleType("amplifier_app_cli.paths")
        paths.create_config_manager = Settings
        with patch.dict(sys.modules, {"amplifier_app_cli": package, "amplifier_app_cli.lib": lib, "amplifier_app_cli.lib.settings": settings, "amplifier_app_cli.paths": paths, "amplifier_app_cli.provider_loader": loader}):
            result = inventory.inventory("configured")
        self.assertEqual({"ok": True, "models": [{"id": "review-6", "source": "provider_supported", "availability": "unknown"}]}, result)
        self.assertEqual(1, len(calls))
        self.assertEqual(("provider.module", {"token": "secret"}), (calls[0][0], calls[0][2]))
        self.assertIsInstance(calls[0][1], Settings)
        self.assertNotIn("secret", json.dumps(result))

    def test_adapter_failure_and_unknown_entry_are_safe(self):
        class BrokenSettings:
            def get_provider_overrides(self):
                raise RuntimeError("token=do-not-leak")

        settings = types.ModuleType("amplifier_app_cli.lib.settings")
        settings.AppSettings = BrokenSettings
        loader = types.ModuleType("amplifier_app_cli.provider_loader")
        loader.get_provider_models = lambda *args, **kwargs: []
        paths = types.ModuleType("amplifier_app_cli.paths")
        paths.create_config_manager = BrokenSettings
        package, lib = types.ModuleType("amplifier_app_cli"), types.ModuleType("amplifier_app_cli.lib")
        with patch.dict(sys.modules, {"amplifier_app_cli": package, "amplifier_app_cli.lib": lib, "amplifier_app_cli.lib.settings": settings, "amplifier_app_cli.paths": paths, "amplifier_app_cli.provider_loader": loader}):
            failure = inventory.inventory("missing")
        self.assertEqual("inventory_unavailable", failure["code"])
        self.assertNotIn("token", json.dumps(failure))

    def test_click_help_and_invalid_args_are_safe_without_discovery(self):
        runner = CliRunner()
        help_result = runner.invoke(resolver.cli, ["--help"])
        self.assertEqual(0, help_result.exit_code)
        self.assertIn("--request", help_result.output)
        invalid = runner.invoke(resolver.cli, ["--id", "one", "--provider", "two"])
        self.assertEqual(1, invalid.exit_code)
        self.assertEqual("usage_error", json.loads(invalid.output)["code"])
        malformed = runner.invoke(resolver.cli, ["--unrecognized", "secret-selector"])
        self.assertEqual(1, malformed.exit_code)
        self.assertEqual("usage_error", json.loads(malformed.output)["code"])
        self.assertNotIn("secret-selector", malformed.output)

    def test_default_resolution_does_not_probe_inventory(self):
        runner = CliRunner()
        with patch.object(resolver, "run_request", return_value=({"ok": True}, 0)) as request:
            result = runner.invoke(resolver.cli, ["--id", "one"])
        self.assertEqual(0, result.exit_code)
        self.assertEqual("one", request.call_args.kwargs["config_id"])
        self.assertNotIn("inventory_loader", request.call_args.kwargs)

    def test_inventory_probes_all_relevant_endpoints_and_marks_partial_results(self):
        providers = [
            {"name": f"provider-{index}", "enabled": True, "behaviors": [], "config_summary": {"type": "openai", "model": "other-model", "priority": str(index), "scope": "project"}}
            for index in range(9)
        ]
        def probe(provider_id, cwd):
            if provider_id == "provider-8":
                return [{"id": "nova-6", "source": "live", "availability": "available"}], True
            return [], False
        with patch.object(discovery, "probe_inventory", side_effect=probe) as mocked:
            records, status, unavailable = discovery.discover_inventories(providers, "/safe", None, [entry["name"] for entry in providers])
        self.assertEqual(9, mocked.call_count)
        self.assertEqual("partial", status)
        self.assertEqual(8, len(unavailable))
        self.assertIn("provider-8", records)
        selected = discovery.resolve_provider(providers, provider="openai", model="nova-6", inventories=records)
        self.assertEqual("provider-8", selected["provider_id"])

    def test_stdlib_discovery_run_request_accepts_an_injected_runner_without_click(self):
        providers = [{"name": "one", "enabled": True, "behaviors": [], "config_summary": {"type": "openai", "model": "review", "priority": "1", "scope": "project"}}]
        complete = subprocess.CompletedProcess([], 0, stdout=json.dumps(providers), stderr="secret")
        payload, status = discovery.run_request(config_id="one", cwd="/safe", command_runner=lambda *args, **kwargs: complete)
        self.assertEqual((0, "one", "review"), (status, payload["provider_id"], payload["model"]))
        self.assertEqual("not_requested", payload["discovery_status"])
        self.assertNotIn("secret", json.dumps(payload))

    def test_models_json_bypasses_adapter_and_loads_provider_list_once(self):
        providers = [{"name": "one", "enabled": True, "behaviors": [], "config_summary": {"type": "openai", "model": "review", "priority": "1", "scope": "project"}}]
        complete = subprocess.CompletedProcess([], 0, stdout=json.dumps(providers), stderr="secret")
        runner = CliRunner()
        with patch.object(discovery.subprocess, "run", return_value=complete) as run:
            result = runner.invoke(resolver.cli, ["--provider", "openai", "--model", "review", "--models-json", '{"one":{"models":[{"id":"review","source":"supplied","available":true}]}}'])
        self.assertEqual(0, result.exit_code)
        self.assertTrue(json.loads(result.output)["ok"])
        self.assertEqual(1, run.call_count)


if __name__ == "__main__":
    unittest.main()
