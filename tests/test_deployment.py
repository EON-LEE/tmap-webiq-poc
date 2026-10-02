import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location(
    "deploy_voice_app", Path(__file__).resolve().parents[1] / "scripts" / "deploy_voice_app.py"
)
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


def resources():
    names = (
        "GWB_PROJECT_ENDPOINT", "TMAP_VOICE_ENDPOINT",
        "TMAP_BING_AGENT_NAME", "TMAP_BING_AGENT_VERSION",
        "TMAP_WEBIQ_AGENT_NAME", "TMAP_WEBIQ_AGENT_VERSION",
    )
    app = {
        "identity": {"type": "SystemAssigned"},
        "properties": {
            "configuration": {"ingress": {"targetPort": 8000, "fqdn": "app.example.invalid"}},
            "template": {"containers": [{"env": [{"name": n, "value": "configured"} for n in names]}]},
        },
    }
    auth = {
        "platform": {"enabled": True},
        "globalValidation": {"unauthenticatedClientAction": "RedirectToLoginPage", "excludedPaths": ["/healthz"]},
        "identityProviders": {"azureActiveDirectory": {"enabled": True, "registration": {"clientId": "sign-in-app"}}},
    }
    return app, auth


class DeploymentTests(unittest.TestCase):
    def args(self, apply=False, allow_anonymous=False):
        return SimpleNamespace(
            subscription="explicit-test-subscription", resource_group="test-rg",
            registry="test-registry", name="test-app", tag="test", apply=apply, allow_anonymous=allow_anonymous,
        )

    def test_default_is_entirely_offline(self):
        inspect, execute = Mock(), Mock()
        deployment.deploy(self.args(), inspect=inspect, execute=execute)
        inspect.assert_not_called()
        execute.assert_not_called()

    def test_anonymous_app_is_not_updated(self):
        for change in (
            {"unauthenticatedClientAction": "AllowAnonymous"},
            {"unauthenticatedClientAction": None},
            {"requireAuthentication": False},
        ):
            with self.subTest(change=change):
                app, auth = resources()
                auth["globalValidation"].update(change)
                with self.assertRaises(deployment.DeploymentError):
                    deployment.validate_existing(app, auth)

    def test_container_apps_auth_shape_is_accepted_without_app_service_only_fields(self):
        app, auth = resources()
        self.assertEqual(deployment.validate_existing(app, {"properties": auth}), "https://app.example.invalid")

    def test_public_demo_needs_the_explicit_flag_and_keeps_other_checks(self):
        app, auth = resources()
        auth["platform"]["enabled"] = False
        with self.assertRaises(deployment.DeploymentError):
            deployment.validate_existing(app, auth)
        self.assertEqual(deployment.validate_existing(app, auth, allow_anonymous=True), "https://app.example.invalid")
        app["properties"]["template"]["containers"][0]["env"] = []
        with self.assertRaises(deployment.DeploymentError):
            deployment.validate_existing(app, auth, allow_anonymous=True)

    def test_public_demo_deploys_with_the_flag(self):
        app, auth = resources()
        auth["platform"]["enabled"] = False
        inspect = Mock(side_effect=[app, auth, {"loginServer": "registry.example.invalid"}])
        execute = Mock()
        deployment.deploy(self.args(apply=True, allow_anonymous=True), inspect=inspect, execute=execute)
        self.assertEqual(execute.call_count, 2)

    def test_entra_provider_must_be_registered_and_not_disabled(self):
        for provider in ({"enabled": False, "registration": {"clientId": "sign-in-app"}}, {"enabled": True}, {}):
            with self.subTest(provider=provider):
                app, auth = resources()
                auth["identityProviders"]["azureActiveDirectory"] = provider
                with self.assertRaises(deployment.DeploymentError):
                    deployment.validate_existing(app, auth)

    def test_voice_auth_exemptions_and_wildcards_are_rejected(self):
        for excluded in ("/ws/voice", "/ws/*", "/*", "*"):
            with self.subTest(excluded=excluded):
                app, auth = resources()
                auth["globalValidation"]["excludedPaths"] = [excluded]
                with self.assertRaises(deployment.DeploymentError):
                    deployment.validate_existing(app, auth)

    def test_all_commands_pin_subscription_and_no_provisioning(self):
        app, auth = resources()
        inspect = Mock(side_effect=[app, auth, {"loginServer": "registry.example.invalid"}])
        execute = Mock()
        deployment.deploy(self.args(apply=True), inspect=inspect, execute=execute)
        commands = [call.args[0] for call in inspect.call_args_list + execute.call_args_list]
        for command in commands:
            i = command.index("--subscription")
            self.assertEqual(command[i + 1], "explicit-test-subscription")
            self.assertNotIn("create", command)
            self.assertNotIn("assignment", command)
        self.assertEqual(execute.call_count, 2)

    def test_missing_agent_settings_are_rejected(self):
        app, auth = resources()
        app["properties"]["template"]["containers"][0]["env"] = []
        with self.assertRaises(deployment.DeploymentError):
            deployment.validate_existing(app, auth)


if __name__ == "__main__":
    unittest.main()
