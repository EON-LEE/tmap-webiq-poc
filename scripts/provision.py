"""Create or update a complete TMAP WebIQ POC environment with one command.

Without --apply the script only reads: sign-in, resource names, model quota and an ARM what-if.
With --apply it runs, in order: resource providers and resource group, shared resources
(infra/main.bicep), the WebIQ project connection, the two search agents, the container image,
the Entra sign-in app, the Container App with sign-in required, and a health check.
Running it again converges to the same environment. The WebIQ key and the sign-in client
secret stay in memory and travel only in HTTPS request bodies, never in command lines or output.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tmap_poc.profiles import PROVIDER_LABELS, WEBIQ_MCP_URL, agent_definition  # noqa: E402

ARM = "https://management.azure.com"
ARM_RESOURCE = "https://management.azure.com/"
GRAPH = "https://graph.microsoft.com/v1.0"
GRAPH_RESOURCE = "https://graph.microsoft.com/"
FOUNDRY_RESOURCE = "https://ai.azure.com/"
AZURE_CLI_APP_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
SIGN_IN_SECRET = "aad-client-secret"
SIGN_IN_SCOPE = "user_impersonation"
WEBIQ_CONNECTION = "webiq-mcp"
AGENT_NAMES = {"bing": "tmap-voice-bing", "webiq": "tmap-voice-webiq"}
WEB_SEARCH_TOOLBOX = "tmap-web-search"
WEB_SEARCH_TOOLS = [{"type": "web_search", "user_location": {"type": "approximate", "country": "KR"}}]
TAGS = {"workload": "tmap-webiq-poc", "environment": "poc"}
RESOURCE_PROVIDERS = (
    "Microsoft.App", "Microsoft.Bing", "Microsoft.CognitiveServices",
    "Microsoft.ContainerRegistry", "Microsoft.ManagedIdentity", "Microsoft.OperationalInsights",
)
API_DEPLOYMENTS = "2024-03-01"
API_GROUPS = "2021-04-01"
API_PROVIDERS = "2021-04-01"
API_FOUNDRY = "2025-06-01"
API_USAGES = "2023-05-01"
API_APPS = "2024-03-01"
TRANSIENT = (429, 500, 502, 503, 504)
# New role assignments, DNS names and Entra objects take minutes to become visible.
PROPAGATING = TRANSIENT + (401, 403)
NAME_PATTERN = re.compile(r"[a-z](?:[a-z0-9]|-(?!-)){1,22}[a-z0-9]")
STEPS = (
    "Register resource providers and create the resource group",
    "Deploy shared resources: Foundry account, project, model, Grounding with Bing, registry, "
    "Container Apps environment, managed identity and roles",
    "Store the WebIQ key in the project connection",
    "Create or reuse the two search agents and the web search toolbox",
    "Build the container image in the registry",
    "Create or update the Entra sign-in app",
    "Deploy the Container App with sign-in required",
    "Check /healthz and that /api/config requires sign-in",
)


class ProvisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Names:
    app: str
    environment: str
    identity: str
    workspace: str
    account: str
    project: str
    registry: str
    bing: str
    bing_connection: str
    sign_in: str

    @classmethod
    def derive(cls, subscription_id, resource_group, name):
        if not NAME_PATTERN.fullmatch(name):
            raise ProvisionError(
                "--name must be 3-24 lowercase letters, digits or single hyphens, "
                "start with a letter and end with a letter or digit."
            )
        # Registry and Foundry names are global, so a stable suffix keeps them unique per environment.
        suffix = hashlib.sha256(f"{subscription_id}/{resource_group}/{name}".lower().encode()).hexdigest()[:6]
        compact = name.replace("-", "")[:16]
        return cls(
            app=name, environment=f"{name}-env", identity=f"{name}-runtime", workspace=f"{name}-logs",
            account=f"{compact}ai{suffix}", project=name, registry=f"{compact}{suffix}",
            bing=f"{name}-bing-{suffix}", bing_connection="bing-grounding", sign_in=f"{name}-login",
        )

    def template_value(self):
        return {
            "app": self.app, "environment": self.environment, "identity": self.identity,
            "workspace": self.workspace, "account": self.account, "project": self.project,
            "registry": self.registry, "bing": self.bing, "bingConnection": self.bing_connection,
        }


@dataclass(frozen=True)
class Context:
    subscription_id: str
    subscription_name: str
    resource_group: str
    location: str
    names: Names
    model: dict
    deployer_id: str
    deployer_type: str

    @property
    def group_path(self):
        return f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"

    @property
    def account_path(self):
        return f"{self.group_path}/providers/Microsoft.CognitiveServices/accounts/{self.names.account}"

    @property
    def project_path(self):
        return f"{self.account_path}/projects/{self.names.project}"

    @property
    def app_path(self):
        return f"{self.group_path}/providers/Microsoft.App/containerApps/{self.names.app}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _quote(expression):
    return urllib.parse.quote(expression, safe="")


def _short(url):
    return url.split("?", 1)[0]


class Azure:
    """Azure CLI for sign-in, tokens and builds; HTTPS for everything that may carry a secret."""

    def __init__(self, subscription, *, run=subprocess.run, urlopen=urllib.request.urlopen,
                 open_public=None, sleep=time.sleep, clock=time.monotonic):
        self.subscription = subscription
        self._run = run
        self._urlopen = urlopen
        self.open_public = open_public or urllib.request.build_opener(_NoRedirect).open
        self.sleep = sleep
        self.clock = clock
        self._tokens = {}
        self._secrets = []

    def secret(self, value):
        """Remember a secret so that no error message can repeat it."""
        if value:
            self._secrets.append(value)
        return value

    def scrub(self, text):
        for value in self._secrets:
            text = text.replace(value, "<redacted>")
        return text

    def az(self, *arguments):
        binary = os.environ.get("TMAP_AZ_BINARY") or shutil.which("az")
        if not binary:
            raise ProvisionError("Install the Azure CLI and sign in with 'az login'.")
        result = self._run(
            [binary, *arguments, "--only-show-errors"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            detail = self.scrub((result.stderr or result.stdout or "").strip())[-1000:]
            raise ProvisionError(f"az {' '.join(arguments[:2])} failed: {detail}")
        return result.stdout

    def az_json(self, *arguments):
        output = self.az(*arguments, "--output", "json")
        return json.loads(output) if output.strip() else None

    def token(self, resource):
        token, expires = self._tokens.get(resource, (None, 0.0))
        if token and expires - time.time() > 300:
            return token
        data = self.az_json(
            "account", "get-access-token", "--subscription", self.subscription, "--resource", resource,
        )
        self._tokens[resource] = (data["accessToken"], float(data.get("expires_on") or time.time() + 1800))
        return data["accessToken"]

    def request(self, method, url, resource, body=None, *, allow=(), retry=TRANSIENT, wait=180):
        data = None if body is None else json.dumps(body).encode()
        deadline = self.clock() + wait
        delay = 5
        while True:
            request = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {self.token(resource)}", "Content-Type": "application/json",
            })
            try:
                with self._urlopen(request, timeout=120) as response:
                    raw = response.read()
                    return response.status, (json.loads(raw) if raw else {}), response.headers
            except urllib.error.HTTPError as error:
                # Redact before shortening so a secret cut at the boundary cannot leak in part.
                detail = self.scrub(error.read().decode("utf-8", "replace"))[:600]
                if error.code in allow:
                    return error.code, {}, error.headers
                if error.code in retry and self.clock() < deadline:
                    self.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                raise ProvisionError(f"{method} {_short(url)} returned HTTP {error.code}: {detail}") from None
            except urllib.error.URLError as error:
                if self.clock() < deadline:
                    self.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                raise ProvisionError(f"{method} {_short(url)} failed: {error.reason}") from None

    def arm(self, method, path, api_version, body=None, **options):
        separator = "&" if "?" in path else "?"
        return self.request(method, f"{ARM}{path}{separator}api-version={api_version}", ARM_RESOURCE, body, **options)

    def graph(self, method, path, body=None, **options):
        return self.request(method, f"{GRAPH}{path}", GRAPH_RESOURCE, body, **options)


def resolve(azure, args):
    account = azure.az_json("account", "show", "--subscription", args.subscription)
    azure.subscription = account["id"]
    user = account.get("user") or {}
    if user.get("type") == "servicePrincipal":
        _, found, _ = azure.graph("GET", "/servicePrincipals?$filter=" + _quote(f"appId eq '{user['name']}'") + "&$select=id")
        deployer, kind = found["value"][0]["id"], "ServicePrincipal"
    else:
        _, me, _ = azure.graph("GET", "/me?$select=id")
        deployer, kind = me["id"], "User"
    model = {
        "name": args.model, "version": args.model_version,
        "sku": args.model_sku, "capacity": args.model_capacity,
    }
    names = Names.derive(account["id"], args.resource_group, args.name)
    return Context(account["id"], account.get("name", ""), args.resource_group, args.location,
                   names, model, deployer, kind)


def missing_providers(azure, ctx):
    missing = []
    for namespace in RESOURCE_PROVIDERS:
        _, provider, _ = azure.arm("GET", f"/subscriptions/{ctx.subscription_id}/providers/{namespace}", API_PROVIDERS)
        if provider.get("registrationState") != "Registered":
            missing.append(namespace)
    return missing


def register_providers(azure, ctx, namespaces):
    for namespace in namespaces:
        azure.arm("POST", f"/subscriptions/{ctx.subscription_id}/providers/{namespace}/register", API_PROVIDERS)
    deadline = azure.clock() + 900
    pending = list(namespaces)
    while pending:
        pending = [name for name in pending if azure.arm(
            "GET", f"/subscriptions/{ctx.subscription_id}/providers/{name}", API_PROVIDERS,
        )[1].get("registrationState") != "Registered"]
        if pending and azure.clock() > deadline:
            raise ProvisionError("Resource providers are still registering: " + ", ".join(pending))
        if pending:
            azure.sleep(15)


def group_exists(azure, ctx):
    status, _, _ = azure.arm("GET", ctx.group_path, API_GROUPS, allow=(404,))
    return status == 200


def available_quota(azure, ctx):
    """Capacity this environment can use, counting what its own deployment already holds."""
    _, usages, _ = azure.arm(
        "GET", f"/subscriptions/{ctx.subscription_id}/providers/Microsoft.CognitiveServices/locations/{ctx.location}/usages",
        API_USAGES,
    )
    key = f"OpenAI.{ctx.model['sku']}.{ctx.model['name']}"
    usage = next((item for item in usages.get("value", []) if item.get("name", {}).get("value") == key), None)
    if usage is None:
        return None
    status, deployment, _ = azure.arm(
        "GET", f"{ctx.account_path}/deployments/{ctx.model['name']}", API_FOUNDRY, allow=(404,),
    )
    held = deployment.get("sku", {}).get("capacity", 0) if status == 200 else 0
    return int(usage["limit"] - usage["currentValue"] + held)


def compile_template(azure):
    return json.loads(azure.az("bicep", "build", "--file", str(ROOT / "infra" / "main.bicep"), "--stdout"))


def parameters(ctx, **application):
    values = {
        "location": ctx.location, "names": ctx.names.template_value(), "model": ctx.model,
        "deployerPrincipalId": ctx.deployer_id, "deployerPrincipalType": ctx.deployer_type,
        **application,
    }
    return {key: {"value": value} for key, value in values.items()}


def what_if(azure, ctx, template, params):
    path = f"{ctx.group_path}/providers/Microsoft.Resources/deployments/tmap-plan/whatIf"
    body = {"properties": {"mode": "Incremental", "template": template, "parameters": params}}
    status, result, headers = azure.arm("POST", path, API_DEPLOYMENTS, body)
    location = headers.get("Location") if status == 202 else None
    deadline = azure.clock() + 600
    while location:
        azure.sleep(5)
        status, result, headers = azure.request("GET", location, ARM_RESOURCE)
        if status == 200:
            break
        if azure.clock() > deadline:
            raise ProvisionError("The what-if check did not finish within 10 minutes.")
    # ARM answers a failed what-if with HTTP 200, so the body decides.
    if result.get("error") or result.get("status") not in (None, "Succeeded"):
        error = result.get("error") or {}
        details = "; ".join(
            f"{item.get('code', '')} {item.get('message', '')}".strip() for item in error.get("details") or []
        )
        raise ProvisionError(azure.scrub(
            f"The what-if check failed: {error.get('code', result.get('status'))} {error.get('message', '')} {details}".strip()
        )[:1200])
    changes = (result.get("properties") or result).get("changes", [])
    return Counter(change.get("changeType", "Unknown") for change in changes)


def deploy(azure, ctx, template, params, label):
    name = f"tmap-{label}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
    path = f"{ctx.group_path}/providers/Microsoft.Resources/deployments/{name}"
    azure.arm("PUT", path, API_DEPLOYMENTS, {
        "properties": {"mode": "Incremental", "template": template, "parameters": params},
    })
    deadline = azure.clock() + 3600
    while True:
        _, deployment, _ = azure.arm("GET", path, API_DEPLOYMENTS)
        properties = deployment.get("properties", {})
        state = properties.get("provisioningState")
        if state == "Succeeded":
            return {key: item.get("value") for key, item in (properties.get("outputs") or {}).items()}
        if state in ("Failed", "Canceled"):
            raise ProvisionError(azure.scrub(f"Deployment {name} {state}: {deployment_errors(azure, path)}"))
        if azure.clock() > deadline:
            raise ProvisionError(f"Deployment {name} did not finish within 60 minutes.")
        azure.sleep(15)


def deployment_errors(azure, path):
    _, operations, _ = azure.arm("GET", f"{path}/operations", API_DEPLOYMENTS)
    messages = []
    for operation in operations.get("value", []):
        properties = operation.get("properties", {})
        if properties.get("provisioningState") != "Failed":
            continue
        target = (properties.get("targetResource") or {}).get("resourceName", "")
        error = (properties.get("statusMessage") or {}).get("error") or {}
        messages.append(azure.scrub(f"{target}: {error.get('code', '')} {error.get('message', '')}".strip())[:400])
    return "; ".join(messages) or "see the deployment in the Azure portal"


def webiq_key(*, prompt):
    key = os.environ.get("WEBIQ_API_KEY", "").strip()
    if not key and prompt and sys.stdin.isatty():
        key = getpass.getpass("WebIQ API key (hidden; Enter keeps an existing connection): ").strip()
    return key or None


def check_webiq_key(azure, key):
    """One tools/list call, so a rejected key never replaces a working connection."""
    request = urllib.request.Request(WEBIQ_MCP_URL, method="POST", data=json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
    }).encode(), headers={
        "x-apikey": key, "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
    })
    try:
        with azure._urlopen(request, timeout=30):
            return
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ProvisionError(f"WebIQ rejected the key (HTTP {error.code}). Check WEBIQ_API_KEY.") from None
        raise ProvisionError(f"The WebIQ key check returned HTTP {error.code}.") from None
    except urllib.error.URLError as error:
        raise ProvisionError(f"The WebIQ key check failed: {error.reason}") from None


def put_webiq_connection(azure, connection_path, key):
    azure.arm("PUT", connection_path, API_FOUNDRY, {"properties": {
        "category": "CustomKeys",
        "target": WEBIQ_MCP_URL,
        "authType": "CustomKeys",
        "isSharedToAll": False,
        "credentials": {"keys": {"x-apikey": key}},
        "metadata": {"purpose": "WebIQ MCP server for the TMAP POC"},
    }})


def ensure_webiq_connection(azure, ctx, key):
    path = f"{ctx.project_path}/connections/{WEBIQ_CONNECTION}"
    status, _, _ = azure.arm("GET", path, API_FOUNDRY, allow=(404,))
    if key is None:
        if status == 404:
            raise ProvisionError("Set WEBIQ_API_KEY (or run in a terminal to type it) to create the WebIQ connection.")
        return "kept"
    put_webiq_connection(azure, path, key)
    return "created" if status == 404 else "updated"


def ensure_agents(azure, ctx, outputs, *, definition=agent_definition):
    """Reuse the latest agent version when it already matches; otherwise add a version."""
    endpoint = outputs["projectEndpoint"]
    connections = {"bing": outputs["bingConnectionId"], "webiq": outputs["webiqConnectionId"]}
    agents = {}
    for provider in PROVIDER_LABELS:
        name = AGENT_NAMES[provider]
        desired = definition(provider, ctx.model["name"], connections[provider])
        status, agent, _ = azure.request(
            "GET", f"{endpoint}/agents/{name}?api-version=v1", FOUNDRY_RESOURCE,
            allow=(404,), retry=PROPAGATING, wait=900,
        )
        latest = ((agent.get("versions") or {}).get("latest") or {}) if status == 200 else {}
        current = latest.get("definition") or {}
        if latest and all(current.get(key) == value for key, value in desired.items()):
            agents[provider] = {"name": name, "version": str(latest["version"])}
            continue
        _, created, _ = azure.request(
            "POST", f"{endpoint}/agents/{name}/versions?api-version=v1", FOUNDRY_RESOURCE,
            {"definition": desired, "description": f"TMAP voice comparison agent using {provider}"},
            retry=PROPAGATING, wait=900,
        )
        agents[provider] = {"name": name, "version": str(created["version"])}
    return agents


def _contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(_contains(actual.get(key), value) for key, value in expected.items())
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(actual) == len(expected)
                and all(_contains(item, wanted) for item, wanted in zip(actual, expected)))
    return actual == expected


def ensure_web_search_toolbox(azure, outputs):
    """Bing-based Web Search that the app server calls over MCP for End-to-end Bing."""
    endpoint = outputs["projectEndpoint"]
    status, toolbox, _ = azure.request(
        "GET", f"{endpoint}/toolboxes/{WEB_SEARCH_TOOLBOX}?api-version=v1", FOUNDRY_RESOURCE,
        allow=(404,), retry=PROPAGATING, wait=900,
    )
    if status == 200:
        candidates = (toolbox, toolbox.get("latest"), (toolbox.get("versions") or {}).get("latest"))
        if any(isinstance(item, dict) and _contains(item.get("tools"), WEB_SEARCH_TOOLS) for item in candidates):
            return "kept"
    azure.request(
        "POST", f"{endpoint}/toolboxes/{WEB_SEARCH_TOOLBOX}/versions?api-version=v1", FOUNDRY_RESOURCE,
        {"tools": WEB_SEARCH_TOOLS}, retry=PROPAGATING, wait=900,
    )
    return "created" if status == 404 else "updated"


def build_image(azure, ctx, outputs, tag):
    image = f"{ctx.names.app}:{tag}"
    azure.az(
        "acr", "build", "--subscription", ctx.subscription_id, "--registry", outputs["registryName"],
        "--image", image, "--file", str(ROOT / "Dockerfile"), "--no-logs", "--output", "none", str(ROOT),
    )
    azure.az_json(
        "acr", "repository", "show", "--subscription", ctx.subscription_id,
        "--name", outputs["registryName"], "--image", image,
    )
    return f"{outputs['registryLoginServer']}/{image}"


def _scope(scope_id):
    return {
        "id": scope_id, "value": SIGN_IN_SCOPE, "type": "User", "isEnabled": True,
        "adminConsentDisplayName": "Access TMAP WebIQ POC", "adminConsentDescription": "Access the TMAP WebIQ POC",
        "userConsentDisplayName": "Access TMAP WebIQ POC", "userConsentDescription": "Access the TMAP WebIQ POC",
    }


def existing_app_secret(azure, ctx):
    status, app, _ = azure.arm("GET", ctx.app_path, API_APPS, allow=(404,))
    if status == 404:
        return None
    configured = (app.get("properties", {}).get("configuration") or {}).get("secrets") or []
    if SIGN_IN_SECRET not in {item.get("name") for item in configured}:
        return None
    _, listed, _ = azure.arm("POST", f"{ctx.app_path}/listSecrets", API_APPS, {})
    value = next((item.get("value") for item in listed.get("value", []) if item.get("name") == SIGN_IN_SECRET), None)
    return azure.secret(value)


def secret_is_current(application, secret, *, margin=timedelta(days=30)):
    """True when the Entra app still holds this secret (matched by its 3-character hint) beyond the margin."""
    soon = datetime.now(timezone.utc) + margin
    for credential in application.get("passwordCredentials") or []:
        hint, end = credential.get("hint"), credential.get("endDateTime")
        if not hint or not end or not secret.startswith(hint):
            continue
        try:
            if datetime.fromisoformat(end.replace("Z", "+00:00")) > soon:
                return True
        except ValueError:
            continue
    return False


def ensure_sign_in_app(azure, ctx, app_url, *, new_secret=False):
    """Single-tenant app whose tokens the Container App accepts; Azure CLI is pre-authorized for checks."""
    redirect = f"{app_url}/.auth/login/aad/callback"
    _, found, _ = azure.graph(
        "GET", "/applications?$filter=" + _quote(f"displayName eq '{ctx.names.sign_in}'")
        + "&$select=id,appId,identifierUris,web,api,passwordCredentials",
    )
    applications = found.get("value", [])
    if len(applications) > 1:
        raise ProvisionError(f"More than one Entra app is named {ctx.names.sign_in}; remove the extras first.")
    created = not applications
    if created:
        _, application, _ = azure.graph("POST", "/applications", {
            "displayName": ctx.names.sign_in,
            "signInAudience": "AzureADMyOrg",
            "web": {"redirectUris": [redirect], "implicitGrantSettings": {
                "enableIdTokenIssuance": True, "enableAccessTokenIssuance": False,
            }},
            "api": {"requestedAccessTokenVersion": 2, "oauth2PermissionScopes": [_scope(str(uuid.uuid4()))]},
        })
    else:
        application = applications[0]
    app_id, object_id = application["appId"], application["id"]
    later = {"retry": TRANSIENT + (404,), "wait": 180}

    web = application.get("web") or {}
    redirects = web.get("redirectUris") or []
    patch = {}
    if redirect not in redirects or not (web.get("implicitGrantSettings") or {}).get("enableIdTokenIssuance"):
        patch["web"] = {"redirectUris": sorted({*redirects, redirect}), "implicitGrantSettings": {
            "enableIdTokenIssuance": True, "enableAccessTokenIssuance": False,
        }}
    if f"api://{app_id}" not in (application.get("identifierUris") or []):
        patch["identifierUris"] = [f"api://{app_id}"]
    api = application.get("api") or {}
    scopes = api.get("oauth2PermissionScopes") or []
    scope = next((item for item in scopes if item.get("value") == SIGN_IN_SCOPE), None)
    if scope is None:
        scope = _scope(str(uuid.uuid4()))
        scopes = [*scopes, scope]
        patch["api"] = {"requestedAccessTokenVersion": 2, "oauth2PermissionScopes": scopes,
                        "preAuthorizedApplications": api.get("preAuthorizedApplications") or []}
    if patch:
        azure.graph("PATCH", f"/applications/{object_id}", patch, **later)
    # A pre-authorization may only name a scope that already exists, so it is a separate update.
    others = [item for item in api.get("preAuthorizedApplications") or [] if item.get("appId") != AZURE_CLI_APP_ID]
    current = next((item for item in api.get("preAuthorizedApplications") or []
                    if item.get("appId") == AZURE_CLI_APP_ID), None)
    if not current or scope["id"] not in (current.get("delegatedPermissionIds") or []):
        azure.graph("PATCH", f"/applications/{object_id}", {"api": {
            "requestedAccessTokenVersion": 2, "oauth2PermissionScopes": scopes,
            "preAuthorizedApplications": [*others, {"appId": AZURE_CLI_APP_ID, "delegatedPermissionIds": [scope["id"]]}],
        }}, **later)

    _, principals, _ = azure.graph("GET", "/servicePrincipals?$filter=" + _quote(f"appId eq '{app_id}'") + "&$select=id")
    if not principals.get("value"):
        azure.graph("POST", "/servicePrincipals", {"appId": app_id}, retry=TRANSIENT + (400, 404), wait=180)

    secret = None if created or new_secret else existing_app_secret(azure, ctx)
    # A stored value that expired or was removed in Entra would deploy a broken sign-in.
    if secret is not None and not secret_is_current(application, secret):
        secret = None
    if secret is None:
        expires = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _, password, _ = azure.graph("POST", f"/applications/{object_id}/addPassword", {
            "passwordCredential": {"displayName": "container-app-auth", "endDateTime": expires},
        }, **later)
        secret = azure.secret(password["secretText"])
    return app_id, secret


def wait_for_app(azure, ctx, timeout=900):
    deadline = azure.clock() + timeout
    while True:
        _, app, _ = azure.arm("GET", ctx.app_path, API_APPS)
        properties = app.get("properties", {})
        latest = properties.get("latestRevisionName")
        if latest and latest == properties.get("latestReadyRevisionName") and properties.get("runningStatus") == "Running":
            return latest
        if azure.clock() > deadline:
            raise ProvisionError(f"Revision {latest} was not ready after {timeout // 60} minutes; check the Container App logs.")
        azure.sleep(15)


def check_sign_in(azure, app_url, attempts=20):
    for _ in range(attempts):
        try:
            with azure.open_public(f"{app_url}/healthz", timeout=30) as response:
                if response.status == 200:
                    break
        except (urllib.error.URLError, OSError):
            pass
        azure.sleep(15)
    else:
        raise ProvisionError(f"{app_url}/healthz did not return HTTP 200.")
    try:
        with azure.open_public(f"{app_url}/api/config", timeout=30) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    if status not in (302, 401):
        raise ProvisionError(f"Sign-in is not enforced: /api/config returned HTTP {status} without a token.")


def describe(ctx, out):
    names, model = ctx.names, ctx.model
    out(f"Subscription: {ctx.subscription_name} ({ctx.subscription_id})")
    out(f"Resource group: {ctx.resource_group} in {ctx.location}")
    out(f"Container App: {names.app} (environment {names.environment}, identity {names.identity})")
    out(f"Foundry: account {names.account}, project {names.project}, "
        f"model {model['name']} {model['version']} {model['sku']} x{model['capacity']}")
    out(f"Grounding with Bing: {names.bing}; registry: {names.registry}; logs: {names.workspace}")
    out(f"Sign-in app: {names.sign_in}; agents: {', '.join(AGENT_NAMES.values())}")


def plan(azure, ctx, template, out):
    out("Plan only: read-only checks, nothing was changed. Add --apply to create or update.")
    describe(ctx, out)
    missing = missing_providers(azure, ctx)
    if missing:
        out("Resource providers to register: " + ", ".join(missing))
    quota = available_quota(azure, ctx)
    if quota is None:
        out("Model quota: unknown for this model and SKU in this region.")
    else:
        verdict = "enough" if quota >= ctx.model["capacity"] else "NOT enough; lower --model-capacity or pick another model"
        out(f"Model quota: {quota} available, {ctx.model['capacity']} requested ({verdict}).")
    source = "WEBIQ_API_KEY" if os.environ.get("WEBIQ_API_KEY", "").strip() else "a hidden prompt, or keep the existing connection"
    out(f"WebIQ key: {source}.")
    if group_exists(azure, ctx):
        counts = what_if(azure, ctx, template, parameters(ctx))
        out("What-if for shared resources: " + (", ".join(f"{kind} {count}" for kind, count in sorted(counts.items())) or "no changes"))
    else:
        out("The resource group does not exist yet; every resource will be created.")
    out("On --apply:")
    for number, step in enumerate(STEPS, 1):
        out(f"  {number}. {step}")


def apply(azure, ctx, template, args, out):
    key = webiq_key(prompt=True)
    if key:
        azure.secret(key)
        check_webiq_key(azure, key)
    quota = available_quota(azure, ctx)
    if quota is not None and quota < ctx.model["capacity"]:
        raise ProvisionError(
            f"Only {quota} {ctx.model['sku']} capacity is available for {ctx.model['name']} in {ctx.location}; "
            f"{ctx.model['capacity']} was requested. Lower --model-capacity or pick another model."
        )
    describe(ctx, out)
    total = len(STEPS)

    out(f"[1/{total}] {STEPS[0]}")
    missing = missing_providers(azure, ctx)
    if missing:
        register_providers(azure, ctx, missing)
    # An existing group keeps its region and tags; resources still go to --location.
    if not group_exists(azure, ctx):
        azure.arm("PUT", ctx.group_path, API_GROUPS, {"location": ctx.location, "tags": TAGS})

    out(f"[2/{total}] {STEPS[1]}")
    outputs = deploy(azure, ctx, template, parameters(ctx), "infra")

    out(f"[3/{total}] {STEPS[2]}")
    out(f"  WebIQ connection {ensure_webiq_connection(azure, ctx, key)}.")

    out(f"[4/{total}] {STEPS[3]}")
    agents = ensure_agents(azure, ctx, outputs)
    out("  " + ", ".join(f"{item['name']}:{item['version']}" for item in agents.values()))
    out(f"  Toolbox {WEB_SEARCH_TOOLBOX} {ensure_web_search_toolbox(azure, outputs)}.")

    out(f"[5/{total}] {STEPS[4]}")
    image = args.image or build_image(azure, ctx, outputs, datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
    out(f"  {image}")

    out(f"[6/{total}] {STEPS[5]}")
    client_id, secret = ensure_sign_in_app(azure, ctx, outputs["appUrl"], new_secret=args.new_sign_in_secret)
    out(f"  client ID {client_id}")

    out(f"[7/{total}] {STEPS[6]}")
    deploy(azure, ctx, template, parameters(
        ctx, deployApp=True, image=image, bingAgent=agents["bing"], webiqAgent=agents["webiq"],
        webSearchToolbox=WEB_SEARCH_TOOLBOX, signInClientId=client_id, signInClientSecret=secret,
    ), "app")
    out(f"  revision {wait_for_app(azure, ctx)}")

    out(f"[8/{total}] {STEPS[7]}")
    check_sign_in(azure, outputs["appUrl"])
    out(f"Ready: {outputs['appUrl']} (Microsoft Entra sign-in required)")
    out("For local development, put these in .env (no secrets):")
    for line in (
        "TMAP_AUTH_MODE=cli",
        f"TMAP_POC_AZ_SUBSCRIPTION={ctx.subscription_id}",
        f"GWB_PROJECT_ENDPOINT={outputs['projectEndpoint']}",
        f"TMAP_VOICE_ENDPOINT=https://{ctx.names.account}.cognitiveservices.azure.com",
        f"TMAP_POC_MODEL_DEPLOYMENT={ctx.model['name']}",
        f"GWB_CONNECTION_ID={outputs['bingConnectionId']}",
        f"WEBIQ_CONNECTION_ID={outputs['webiqConnectionId']}",
        f"TMAP_BING_AGENT_NAME={agents['bing']['name']}",
        f"TMAP_BING_AGENT_VERSION={agents['bing']['version']}",
        f"TMAP_WEBIQ_AGENT_NAME={agents['webiq']['name']}",
        f"TMAP_WEBIQ_AGENT_VERSION={agents['webiq']['version']}",
        f"TMAP_WEB_SEARCH_TOOLBOX={WEB_SEARCH_TOOLBOX}",
    ):
        out(f"  {line}")


def run(args, *, azure=None, out=print):
    azure = azure or Azure(args.subscription)
    ctx = resolve(azure, args)
    template = compile_template(azure)
    if args.apply:
        apply(azure, ctx, template, args, out)
    else:
        plan(azure, ctx, template, out)


def parser():
    result = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    result.add_argument("--subscription", required=True, help="Subscription ID or name.")
    result.add_argument("--resource-group", required=True, help="Resource group for the environment; created if missing.")
    result.add_argument("--location", default="eastus2", help="Region with Voice Live and the model (default: eastus2).")
    result.add_argument("--name", default="tmap-webiq-poc", help="Container App name; other names derive from it.")
    result.add_argument("--model", default="gpt-6-luna")
    result.add_argument("--model-version", default="2026-09-22")
    result.add_argument("--model-sku", default="GlobalStandard")
    result.add_argument("--model-capacity", type=int, default=250, help="Thousands of tokens per minute.")
    result.add_argument("--image", help="Use this image instead of building one (registry/repository:tag).")
    result.add_argument("--new-sign-in-secret", action="store_true",
                        help="Create a new sign-in client secret (valid one year) instead of reusing the current one.")
    result.add_argument("--apply", action="store_true", help="Create or update resources. Without it only read.")
    return result


def main():
    arguments = parser()
    args = arguments.parse_args()
    try:
        run(args)
    except ProvisionError as error:
        arguments.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
