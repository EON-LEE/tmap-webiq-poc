"""Build and update an existing Container App. Sign-in is required unless --allow-anonymous. Dry-run by default."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from tmap_poc.auth import _az_binary

ROOT = Path(__file__).resolve().parents[1]


class DeploymentError(RuntimeError):
    pass


def command(subscription, *arguments):
    return [_az_binary(), *arguments, "--subscription", subscription, "--only-show-errors"]


def read_json(arguments):
    result = subprocess.run(arguments + ["--output", "json"], check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def validate_sign_in(auth):
    if not auth.get("platform", {}).get("enabled"):
        raise DeploymentError("Enable Container Apps authentication before deployment, or pass --allow-anonymous for a public demo.")
    policy = auth.get("globalValidation", {})
    # Container Apps has no requireAuthentication flag; an explicit non-anonymous action enforces sign-in.
    if policy.get("requireAuthentication") is False or policy.get("unauthenticatedClientAction") not in (
        "RedirectToLoginPage", "Return401", "Return403",
    ):
        raise DeploymentError("Require authenticated access, or pass --allow-anonymous for a public demo.")
    excluded = policy.get("excludedPaths", [])
    if not isinstance(excluded, list) or any(path not in ("/healthz", "/favicon.ico") for path in excluded):
        raise DeploymentError("Remove authentication exclusions; only /healthz and /favicon.ico may be exempt.")
    entra = auth.get("identityProviders", {}).get("azureActiveDirectory", {})
    if entra.get("enabled") is False or not entra.get("registration", {}).get("clientId"):
        raise DeploymentError("Configure Microsoft Entra authentication before deployment.")


def validate_existing(app, auth, *, allow_anonymous=False):
    auth = auth.get("properties", auth)
    # A temporary public demo skips only the sign-in checks; identity, ingress and settings are still required.
    if not allow_anonymous:
        validate_sign_in(auth)
    if app.get("identity", {}).get("type", "None") == "None":
        raise DeploymentError("Configure a managed identity and its Foundry/Voice Live permissions first.")
    properties = app.get("properties", {})
    ingress = properties.get("configuration", {}).get("ingress") or {}
    if ingress.get("targetPort") != 8000 or not ingress.get("fqdn") or ingress.get("allowInsecure"):
        raise DeploymentError("Configure HTTPS ingress to target port 8000 first.")
    containers = properties.get("template", {}).get("containers", [])
    if len(containers) != 1:
        raise DeploymentError("This helper only updates a single-container application.")
    env = {item["name"]: item for item in containers[0].get("env", [])}
    required = (
        "GWB_PROJECT_ENDPOINT", "TMAP_VOICE_ENDPOINT",
        "TMAP_BING_AGENT_NAME", "TMAP_BING_AGENT_VERSION",
        "TMAP_WEBIQ_AGENT_NAME", "TMAP_WEBIQ_AGENT_VERSION",
    )
    missing = [name for name in required if not (env.get(name, {}).get("value") or env.get(name, {}).get("secretRef"))]
    if missing:
        raise DeploymentError("Configure application settings first: " + ", ".join(missing))
    if "SystemAssigned" not in app["identity"]["type"] and not env.get("AZURE_CLIENT_ID"):
        raise DeploymentError("Set AZURE_CLIENT_ID for a user-assigned managed identity.")
    return "https://" + ingress["fqdn"]


def deploy(args, *, inspect=read_json, execute=subprocess.run):
    tag = args.tag or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    image = f"{args.name}:{tag}"
    access = "public (no sign-in)" if args.allow_anonymous else "authenticated"
    if not args.apply:
        print("Plan only; no Azure calls or resources changed.")
        print(f"Build Dockerfile in existing ACR '{args.registry}' as {image}.")
        print(f"Update existing {access} Container App '{args.name}'.")
        print("Requires existing identity, registry pull rights"
              + ("" if args.allow_anonymous else ", Entra login") + " and application settings.")
        print("Add --apply to build and update. This helper never creates resources or grants roles.")
        return
    app = inspect(command(
        args.subscription, "containerapp", "show",
        "--name", args.name, "--resource-group", args.resource_group,
    ))
    auth = inspect(command(
        args.subscription, "containerapp", "auth", "show",
        "--name", args.name, "--resource-group", args.resource_group,
    ))
    origin = validate_existing(app, auth, allow_anonymous=args.allow_anonymous)
    if args.allow_anonymous:
        print("Public demo: anyone with the URL can use the app and the Azure services it calls.")
    registry = inspect(command(args.subscription, "acr", "show", "--name", args.registry))
    login_server = registry.get("loginServer")
    if not login_server:
        raise DeploymentError("The registry did not return a login server.")
    execute(command(
        args.subscription, "acr", "build", "--registry", args.registry,
        "--image", image, "--file", str(ROOT / "Dockerfile"), "--no-logs", "--output", "none", str(ROOT),
    ), check=True)
    execute(command(
        args.subscription, "containerapp", "update",
        "--name", args.name, "--resource-group", args.resource_group,
        "--image", f"{login_server}/{image}",
        "--set-env-vars", "TMAP_AUTH_MODE=managed_identity", f"TMAP_ALLOWED_ORIGINS={origin}",
        "--output", "none",
    ), check=True)
    print(f"Image update submitted. Open {origin} after the new revision is ready.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--tag")
    parser.add_argument(
        "--allow-anonymous", action="store_true",
        help="Temporary public demo: update the app even though sign-in is off. Anyone with the URL can use it.",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        deploy(args)
    except DeploymentError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
