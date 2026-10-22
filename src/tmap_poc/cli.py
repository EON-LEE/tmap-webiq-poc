"""Local app and explicit agent configuration."""

import argparse
from dataclasses import replace
import os
from pathlib import Path
import re

from tmap_poc.app_settings import AppSettings
from tmap_poc.config import ConfigError, load_dotenv
from tmap_poc.profiles import PROVIDER_LABELS, agent_definition
from tmap_poc.telemetry import configure_tracing, shutdown_tracing

CONNECTION_ENV = {"bing": "GWB_CONNECTION_ID", "webiq": "WEBIQ_CONNECTION_ID"}


def prepare_agents(settings, prefix, apply):
    settings.require(voice=False)
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]{0,40}", prefix):
        raise ConfigError("Agent prefix must start with a letter and contain only letters, digits or hyphens.")
    for key in CONNECTION_ENV.values():
        if not os.environ.get(key, "").strip() or "<" in os.environ[key]:
            raise ConfigError(f"{key} is required to register the search tools.")
    definitions = {
        provider: agent_definition(provider, settings.model, os.environ[CONNECTION_ENV[provider]])
        for provider in PROVIDER_LABELS
    }
    if not apply:
        print("Plan only. --apply registers new Foundry agent versions; it does not create Azure resources.")
        for provider in definitions:
            print(f"{provider}: {prefix}-{provider} / {settings.model}")
        return
    from azure.ai.projects import AIProjectClient

    credential = settings.credential()
    try:
        with AIProjectClient(endpoint=settings.project_endpoint, credential=credential) as project:
            for provider, definition in definitions.items():
                name = f"{prefix}-{provider}"
                result = project.agents.create_version(agent_name=name, definition=definition)
                print(f"TMAP_{provider.upper()}_AGENT_NAME={name}")
                print(f"TMAP_{provider.upper()}_AGENT_VERSION={result.version}")
    finally:
        close = getattr(credential, "close", None)
        if close is not None:
            close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Foundry voice agent")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Serve the local voice interface")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    agents = commands.add_parser("prepare-agents", help="Plan/register shared voice-ready agents")
    agents.add_argument("--prefix", default="tmap-voice")
    agents.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    load_dotenv(args.env_file)
    try:
        settings = AppSettings.from_env()
        if args.command != "prepare-agents":
            configure_tracing()
        if args.command == "serve":
            import uvicorn
            from tmap_poc.api import create_app

            if not os.environ.get("TMAP_ALLOWED_ORIGINS") and args.host in ("localhost", "127.0.0.1", "::1"):
                settings = replace(settings, allowed_origins=(
                    f"http://localhost:{args.port}", f"http://127.0.0.1:{args.port}",
                    f"http://[::1]:{args.port}",
                ))
            uvicorn.run(create_app(settings), host=args.host, port=args.port, ws_max_size=65536)
        elif args.command == "prepare-agents":
            prepare_agents(settings, args.prefix, args.apply)
    except ConfigError as exc:
        parser.error(str(exc))
    finally:
        shutdown_tracing()


if __name__ == "__main__":
    main()
