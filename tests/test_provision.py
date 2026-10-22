import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


provision = load("provision")
setup_webiq = load("setup_webiq_connection")

SUBSCRIPTION = "00000000-0000-0000-0000-000000000001"
WEBIQ_KEY = "WEBIQ-KEY-NEVER-PRINTED"
NEW_SECRET = "NEW-SIGN-IN-SECRET"
OLD_SECRET = "OLD-SIGN-IN-SECRET"
ENDPOINT = "https://account.services.ai.azure.com/api/projects/tmap-webiq-poc"
OUTPUTS = {
    "projectEndpoint": ENDPOINT,
    "projectId": "/subscriptions/s/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/a/projects/p",
    "bingConnectionId": "/subscriptions/s/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/a/projects/p/connections/bing-grounding",
    "webiqConnectionId": "/subscriptions/s/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/a/projects/p/connections/webiq-mcp",
    "registryName": "registry",
    "registryLoginServer": "registry.azurecr.io",
    "appUrl": "https://tmap-webiq-poc.example.invalid",
}


class Response:
    def __init__(self, status=200, body=None, headers=None):
        self.status = status
        self.headers = headers or {}
        self._raw = b"" if body is None else json.dumps(body).encode()

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def failure(url, status, body=None):
    return urllib.error.HTTPError(url, status, "error", {}, io.BytesIO(json.dumps(body or {}).encode()))


class FakeCloud:
    """Answers the Azure CLI, ARM, Graph, Foundry and WebIQ calls the script makes."""

    def __init__(self, *, group=False, used=0, limit=1000, connection=False, agents=None, toolbox=False,
                 registration=None, app_secret=None, webiq_status=200, deployment_state="Succeeded",
                 what_if_failure=False):
        self.group, self.used, self.limit, self.connection = group, used, limit, connection
        self.agents = agents or {}
        self.toolbox = toolbox
        self.what_if_failure = what_if_failure
        self.registration = registration
        self.app_secret = app_secret
        self.webiq_status = webiq_status
        self.deployment_state = deployment_state
        self.app_deployed = False
        self.commands, self.calls = [], []

    def azure(self):
        return provision.Azure(
            "test-subscription", run=self.run, urlopen=self.urlopen,
            open_public=self.open_public, sleep=lambda _seconds: None,
        )

    def run(self, argv, **_options):
        self.commands.append(argv)
        words = argv[1:]
        if words[:2] == ["account", "show"]:
            out = {"id": SUBSCRIPTION, "name": "Test", "tenantId": "tenant", "user": {"type": "user", "name": "u"}}
        elif words[:2] == ["account", "get-access-token"]:
            out = {"accessToken": "token", "expires_on": time.time() + 3600}
        elif words[:2] == ["bicep", "build"]:
            out = {"resources": {}}
        elif words[:2] == ["acr", "build"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        elif words[:3] == ["acr", "repository", "show"]:
            out = {"digest": "sha256:test"}
        else:
            raise AssertionError(f"unexpected az call {words}")
        return subprocess.CompletedProcess(argv, 0, json.dumps(out), "")

    def open_public(self, url, timeout=None):
        if url.endswith("/healthz"):
            return Response(200)
        raise failure(url, 302)

    def urlopen(self, request, timeout=None):
        method, url = request.get_method(), request.full_url
        body = json.loads(request.data) if request.data else None
        self.calls.append((method, url, body))
        path = url.split("?", 1)[0]
        if url.startswith("https://api.microsoft.ai/"):
            if self.webiq_status != 200:
                raise failure(url, self.webiq_status)
            return Response(200, {"result": {"tools": []}})
        if url.startswith(provision.GRAPH):
            return self.graph(method, path, url, body)
        if url.startswith(ENDPOINT):
            return self.foundry(method, path, url, body)
        return self.arm(method, path, url, body)

    def arm(self, method, path, url, body):
        if re.search(r"/providers/Microsoft\.[A-Za-z]+$", path) and method == "GET":
            return Response(200, {"registrationState": "Registered"})
        if path.endswith("/usages"):
            return Response(200, {"value": [{
                "name": {"value": "OpenAI.GlobalStandard.gpt-6-luna"}, "currentValue": self.used, "limit": self.limit,
            }]})
        if re.search(r"/resourceGroups/[^/]+$", path):
            if method == "PUT":
                self.group = True
                return Response(201, {})
            if not self.group:
                raise failure(url, 404)
            return Response(200, {})
        if "/accounts/" in path and "/deployments/" in path:
            raise failure(url, 404)
        if path.endswith("/whatIf"):
            return Response(202, headers={"Location": "https://management.azure.com/whatif-result"})
        if path.endswith("/whatif-result"):
            if self.what_if_failure:
                return Response(200, {"status": "Failed", "error": {
                    "code": "InvalidTemplate", "message": "bad template",
                    "details": [{"code": "InsufficientQuota", "message": "Not enough quota"}],
                }})
            return Response(200, {"properties": {"changes": [{"changeType": "Create"}, {"changeType": "NoChange"}]}})
        if path.endswith("/operations"):
            return Response(200, {"value": [{"properties": {
                "provisioningState": "Failed", "targetResource": {"resourceName": "connection"},
                "statusMessage": {"error": {"code": "BadRequest", "message": f"rejected {WEBIQ_KEY}"}},
            }}]})
        if "/Microsoft.Resources/deployments/" in path:
            if method == "PUT":
                parameters = body["properties"]["parameters"]
                self.app_deployed = self.app_deployed or parameters.get("deployApp", {}).get("value", False)
                return Response(201, {})
            return Response(200, {"properties": {
                "provisioningState": self.deployment_state,
                "outputs": {key: {"value": value} for key, value in OUTPUTS.items()},
            }})
        if path.endswith("/connections/webiq-mcp"):
            if method == "GET" and not self.connection:
                raise failure(url, 404)
            return Response(200, {})
        if path.endswith("/listSecrets"):
            return Response(200, {"value": [{"name": "aad-client-secret", "value": self.app_secret}]})
        if "/containerApps/" in path:
            if self.app_deployed:
                return Response(200, {"properties": {
                    "latestRevisionName": "r2", "latestReadyRevisionName": "r2", "runningStatus": "Running",
                }})
            if self.app_secret:
                return Response(200, {"properties": {"configuration": {"secrets": [{"name": "aad-client-secret"}]}}})
            raise failure(url, 404)
        raise AssertionError(f"unexpected ARM call {method} {url}")

    def graph(self, method, path, url, body):
        if path.endswith("/me"):
            return Response(200, {"id": "deployer-object-id"})
        if path.endswith("/applications") and method == "GET":
            return Response(200, {"value": [self.registration] if self.registration else []})
        if path.endswith("/applications") and method == "POST":
            self.registration = {"id": "object-id", "appId": "client-id", "identifierUris": [], **body}
            return Response(201, self.registration)
        if path.endswith("/addPassword"):
            return Response(200, {"secretText": NEW_SECRET})
        if method == "PATCH":
            return Response(204)
        if path.endswith("/servicePrincipals"):
            return Response(200 if method == "GET" else 201, {"value": []} if method == "GET" else {})
        raise AssertionError(f"unexpected Graph call {method} {url}")

    def foundry(self, method, path, url, body):
        if "/toolboxes/" in path:
            if method == "POST":
                return Response(200, {"name": provision.WEB_SEARCH_TOOLBOX, "version": "1"})
            if not self.toolbox:
                raise failure(url, 404)
            return Response(200, {"versions": {"latest": {"version": "1", "tools": [
                {**provision.WEB_SEARCH_TOOLS[0], "search_context_size": "medium"},
            ]}}})
        name = path.split("/agents/", 1)[1].split("/", 1)[0]
        if method == "GET":
            if name not in self.agents:
                raise failure(url, 404)
            return Response(200, {"versions": {"latest": self.agents[name]}})
        return Response(200, {"version": "1"})

    def writes(self):
        return [(method, url) for method, url, _ in self.calls if method in ("PUT", "PATCH", "DELETE")]

    def bodies(self, method, fragment):
        return [body for verb, url, body in self.calls if verb == method and fragment in url]


def arguments(*extra):
    return provision.parser().parse_args(["--subscription", "test", "--resource-group", "rg", *extra])


def registration(secret_expires="2099-01-01T00:00:00Z"):
    return {
        "id": "object-id", "appId": "client-id", "identifierUris": ["api://client-id"],
        "web": {"redirectUris": [OUTPUTS["appUrl"] + "/.auth/login/aad/callback"],
                "implicitGrantSettings": {"enableIdTokenIssuance": True}},
        "api": {"oauth2PermissionScopes": [{"id": "scope-id", "value": "user_impersonation"}],
                "preAuthorizedApplications": [{"appId": provision.AZURE_CLI_APP_ID, "delegatedPermissionIds": ["scope-id"]}]},
        "passwordCredentials": [{"hint": OLD_SECRET[:3], "endDateTime": secret_expires}],
    }


def existing_agents():
    return {
        name: {"version": "7", "definition": provision.agent_definition(
            provider, "gpt-6-luna", OUTPUTS[f"{provider}ConnectionId"],
        )}
        for provider, name in provision.AGENT_NAMES.items()
    }


class RunMixin:
    def run_script(self, cloud, *extra, key=None):
        environment = {"TMAP_AZ_BINARY": "az"}
        if key:
            environment["WEBIQ_API_KEY"] = key
        output = io.StringIO()
        with patch.dict("os.environ", environment, clear=False), \
                patch.object(provision.sys, "stdin", io.StringIO()), \
                patch.object(provision.getpass, "getpass", side_effect=AssertionError("prompted")):
            if not key:
                provision.os.environ.pop("WEBIQ_API_KEY", None)
            provision.run(arguments(*extra), azure=cloud.azure(), out=lambda line: print(line, file=output))
        return output.getvalue()


class NameTests(unittest.TestCase):
    def test_names_are_stable_valid_and_unique_per_resource_group(self):
        first = provision.Names.derive(SUBSCRIPTION, "rg", "tmap-webiq-poc")
        self.assertEqual(first, provision.Names.derive(SUBSCRIPTION, "rg", "tmap-webiq-poc"))
        self.assertNotEqual(first.registry, provision.Names.derive(SUBSCRIPTION, "rg2", "tmap-webiq-poc").registry)
        self.assertRegex(first.registry, r"^[a-z0-9]{5,50}$")
        self.assertRegex(first.account, r"^[a-z0-9]{2,24}$")
        self.assertEqual((first.app, first.project, first.sign_in), ("tmap-webiq-poc", "tmap-webiq-poc", "tmap-webiq-poc-login"))

    def test_invalid_names_are_rejected(self):
        for name in ("Tmap", "ab", "tmap--poc", "-tmap", "tmap-", "t" * 25):
            with self.subTest(name=name), self.assertRaises(provision.ProvisionError):
                provision.Names.derive(SUBSCRIPTION, "rg", name)


class PlanTests(RunMixin, unittest.TestCase):
    def test_plan_only_reads_and_reports_quota_and_what_if(self):
        cloud = FakeCloud(group=True, used=250, limit=250)
        output = self.run_script(cloud)
        self.assertEqual(cloud.writes(), [])
        self.assertEqual([url for verb, url, _ in cloud.calls if verb == "POST"],
                         [url for verb, url, _ in cloud.calls if verb == "POST" and "/whatIf" in url])
        self.assertFalse(any("build" in command and "acr" in command for command in cloud.commands))
        self.assertIn("Plan only", output)
        self.assertIn("NOT enough", output)
        self.assertIn("What-if for shared resources: Create 1, NoChange 1", output)

    def test_plan_for_a_new_resource_group_skips_what_if(self):
        cloud = FakeCloud()
        output = self.run_script(cloud)
        self.assertIn("every resource will be created", output)
        self.assertFalse(any("/whatIf" in url for _, url, _ in cloud.calls))


class ApplyTests(RunMixin, unittest.TestCase):
    def test_new_environment_runs_every_step_and_keeps_secrets_out_of_commands_and_output(self):
        cloud = FakeCloud()
        output = self.run_script(cloud, "--apply", key=WEBIQ_KEY)

        self.assertIn("Ready: https://tmap-webiq-poc.example.invalid", output)
        for secret in (WEBIQ_KEY, NEW_SECRET):
            self.assertNotIn(secret, output)
            self.assertFalse(any(secret in " ".join(command) for command in cloud.commands))
        connection = cloud.bodies("PUT", "/connections/webiq-mcp")
        self.assertEqual(connection[0]["properties"]["credentials"], {"keys": {"x-apikey": WEBIQ_KEY}})
        others = [body for verb, url, body in cloud.calls if body and "/connections/webiq-mcp" not in url]
        self.assertFalse(any(WEBIQ_KEY in json.dumps(body) for body in others))

        deployments = [body["properties"]["parameters"] for body in cloud.bodies("PUT", "/Microsoft.Resources/deployments/")]
        self.assertEqual(len(deployments), 2)
        self.assertNotIn("deployApp", deployments[0])
        app = deployments[1]
        self.assertTrue(app["deployApp"]["value"])
        self.assertEqual(app["signInClientSecret"]["value"], NEW_SECRET)
        self.assertEqual(app["signInClientId"]["value"], "client-id")
        self.assertEqual(app["image"]["value"][:len("registry.azurecr.io/tmap-webiq-poc:")], "registry.azurecr.io/tmap-webiq-poc:")
        self.assertEqual(app["bingAgent"]["value"], {"name": "tmap-voice-bing", "version": "1"})
        self.assertEqual(app["webSearchToolbox"]["value"], "tmap-web-search")
        self.assertEqual(cloud.bodies("POST", "/toolboxes/"), [{"tools": provision.WEB_SEARCH_TOOLS}])

        created = cloud.bodies("POST", "/agents/")
        self.assertEqual([body["definition"] for body in created], [
            provision.agent_definition("bing", "gpt-6-luna", OUTPUTS["bingConnectionId"]),
            provision.agent_definition("webiq", "gpt-6-luna", OUTPUTS["webiqConnectionId"]),
        ])
        sign_in = cloud.bodies("POST", "/applications")[0]
        self.assertEqual(sign_in["signInAudience"], "AzureADMyOrg")
        self.assertEqual(sign_in["web"]["redirectUris"], [OUTPUTS["appUrl"] + "/.auth/login/aad/callback"])
        preauthorized = [body for body in cloud.bodies("PATCH", "/applications/") if "api" in body]
        self.assertEqual(preauthorized[-1]["api"]["preAuthorizedApplications"][0]["appId"], provision.AZURE_CLI_APP_ID)

        order = [url for verb, url, _ in cloud.calls if verb in ("PUT", "POST")]
        steps = ["/resourceGroups/rg?", "/deployments/tmap-infra-", "/connections/webiq-mcp", "/agents/",
                 "/toolboxes/", "/applications", "/deployments/tmap-app-"]
        positions = [next(index for index, url in enumerate(order) if step in url) for step in steps]
        self.assertEqual(positions, sorted(positions))

    def test_rerun_reuses_matching_agents_connection_and_sign_in_secret(self):
        cloud = FakeCloud(group=True, connection=True, agents=existing_agents(), toolbox=True,
                          registration=registration(), app_secret=OLD_SECRET)
        output = self.run_script(cloud, "--apply", "--image", "registry.azurecr.io/tmap-webiq-poc:old")

        self.assertIn("WebIQ connection kept.", output)
        self.assertIn("tmap-voice-bing:7, tmap-voice-webiq:7", output)
        self.assertIn("Toolbox tmap-web-search kept.", output)
        self.assertEqual(cloud.bodies("POST", "/agents/"), [])
        self.assertEqual(cloud.bodies("POST", "/toolboxes/"), [])
        self.assertEqual(cloud.bodies("POST", "/addPassword"), [])
        self.assertEqual(cloud.bodies("PATCH", "/applications/"), [])
        self.assertFalse(any("acr" in command for command in cloud.commands))
        self.assertEqual([url for verb, url, _ in cloud.calls if verb == "PUT" and "/resourceGroups/rg?" in url], [])
        app = cloud.bodies("PUT", "/deployments/tmap-app-")[0]["properties"]["parameters"]
        self.assertEqual(app["signInClientSecret"]["value"], OLD_SECRET)
        self.assertEqual(app["image"]["value"], "registry.azurecr.io/tmap-webiq-poc:old")
        self.assertNotIn(OLD_SECRET, output)

    def test_new_sign_in_secret_replaces_the_reused_one(self):
        cloud = FakeCloud(group=True, connection=True, agents=existing_agents(), toolbox=True,
                          registration=registration(), app_secret=OLD_SECRET)
        self.run_script(cloud, "--apply", "--image", "registry.azurecr.io/tmap-webiq-poc:old", "--new-sign-in-secret")
        self.assertEqual(len(cloud.bodies("POST", "/addPassword")), 1)
        self.assertFalse(any("/listSecrets" in url for _, url, _ in cloud.calls))
        app = cloud.bodies("PUT", "/deployments/tmap-app-")[0]["properties"]["parameters"]
        self.assertEqual(app["signInClientSecret"]["value"], NEW_SECRET)

    def test_expiring_or_unknown_stored_secret_is_replaced(self):
        for credentials in ("2026-01-01T00:00:00Z", None):
            with self.subTest(credentials=credentials):
                current = registration(credentials or "2099-01-01T00:00:00Z")
                if credentials is None:
                    current["passwordCredentials"] = [{"hint": "zzz", "endDateTime": "2099-01-01T00:00:00Z"}]
                cloud = FakeCloud(group=True, connection=True, agents=existing_agents(), toolbox=True,
                                  registration=current, app_secret=OLD_SECRET)
                self.run_script(cloud, "--apply", "--image", "registry.azurecr.io/tmap-webiq-poc:old")
                self.assertEqual(len(cloud.bodies("POST", "/addPassword")), 1)
                app = cloud.bodies("PUT", "/deployments/tmap-app-")[0]["properties"]["parameters"]
                self.assertEqual(app["signInClientSecret"]["value"], NEW_SECRET)

    def test_failed_what_if_is_an_error_not_no_changes(self):
        cloud = FakeCloud(group=True, what_if_failure=True)
        with self.assertRaisesRegex(provision.ProvisionError, "InvalidTemplate.*InsufficientQuota"):
            self.run_script(cloud)

    def test_secret_is_redacted_before_a_message_is_shortened(self):
        cloud, secret = FakeCloud(), "S3cr3t-Value-That-Crosses-The-Cut"

        def rejecting(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 400, "bad", {}, io.BytesIO(("x" * 590 + secret).encode()))

        azure = provision.Azure("test", run=cloud.run, urlopen=rejecting, sleep=lambda _seconds: None)
        azure.secret(secret)
        with patch.dict("os.environ", {"TMAP_AZ_BINARY": "az"}), self.assertRaises(provision.ProvisionError) as caught:
            azure.request("GET", "https://management.azure.com/thing", provision.ARM_RESOURCE)
        self.assertNotIn(secret[:4], str(caught.exception))
        self.assertIn("<redacted>", str(caught.exception))

    def test_missing_connection_without_key_fails_after_shared_resources(self):
        cloud = FakeCloud()
        with self.assertRaisesRegex(provision.ProvisionError, "WEBIQ_API_KEY"):
            self.run_script(cloud, "--apply")

    def test_quota_shortage_stops_before_any_change(self):
        cloud = FakeCloud(used=250, limit=250)
        with self.assertRaisesRegex(provision.ProvisionError, "Lower --model-capacity"):
            self.run_script(cloud, "--apply", key=WEBIQ_KEY)
        self.assertEqual(cloud.writes(), [])

    def test_rejected_webiq_key_stops_before_any_change(self):
        cloud = FakeCloud(webiq_status=401)
        with self.assertRaises(provision.ProvisionError) as caught:
            self.run_script(cloud, "--apply", key=WEBIQ_KEY)
        self.assertIn("WebIQ rejected the key", str(caught.exception))
        self.assertNotIn(WEBIQ_KEY, str(caught.exception))
        self.assertEqual(cloud.writes(), [])

    def test_failed_deployment_reports_operations_without_secrets(self):
        cloud = FakeCloud(deployment_state="Failed")
        with self.assertRaises(provision.ProvisionError) as caught:
            self.run_script(cloud, "--apply", key=WEBIQ_KEY)
        message = str(caught.exception)
        self.assertIn("BadRequest", message)
        self.assertIn("<redacted>", message)
        self.assertNotIn(WEBIQ_KEY, message)


class SetupWebIQConnectionTests(unittest.TestCase):
    CONNECTION = ("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.CognitiveServices"
                  "/accounts/account/projects/project/connections/webiq-mcp")

    def test_plan_changes_nothing(self):
        lines = []
        setup_webiq.main(["--connection-id", self.CONNECTION], out=lines.append)
        self.assertIn("Plan only", lines[0])

    def test_apply_checks_then_stores_key_without_printing_it(self):
        cloud, lines = FakeCloud(connection=True), []
        with patch.dict("os.environ", {"WEBIQ_API_KEY": WEBIQ_KEY, "TMAP_AZ_BINARY": "az"}):
            setup_webiq.main(["--connection-id", self.CONNECTION, "--apply"], azure=cloud.azure(), out=lines.append)
        self.assertEqual([verb for verb, _, _ in cloud.calls], ["POST", "PUT"])
        self.assertEqual(cloud.calls[1][2]["properties"]["credentials"]["keys"]["x-apikey"], WEBIQ_KEY)
        self.assertNotIn(WEBIQ_KEY, " ".join(lines))

    def test_rejects_other_resource_ids(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            setup_webiq.main(["--connection-id", "/subscriptions/sub/resourceGroups/rg"])


if __name__ == "__main__":
    unittest.main()
