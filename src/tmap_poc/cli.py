"""Local app, explicit agent configuration, and shared text comparisons."""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

from tmap_poc.app_settings import AppSettings
from tmap_poc.config import ConfigError, load_dotenv
from tmap_poc.profiles import NAVIGATION_INSTRUCTIONS, PROVIDER_LABELS, agent_definition
from tmap_poc.telemetry import configure_tracing, shutdown_tracing, span, trace_id


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_agents(settings, prefix, apply):
    settings.require(voice=False)
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]{0,40}", prefix):
        raise ConfigError("Agent prefix must start with a letter and contain only letters, digits or hyphens.")
    for key in ("GWB_CONNECTION_ID", "WEBIQ_CONNECTION_ID"):
        if not os.environ.get(key, "").strip() or "<" in os.environ[key]:
            raise ConfigError(f"{key} is required to register the search tools.")
    definitions = {
        provider: agent_definition(provider, settings.model) for provider in PROVIDER_LABELS
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


def verified_profiles(project, settings):
    snapshots = {}
    for provider, reference in settings.agents.items():
        deployed = project.agents.get_version(reference.name, reference.version)
        definition = deployed.definition.as_dict()
        expected_type = "bing_grounding" if provider == "bing" else "mcp"
        tools = definition.get("tools", [])
        if (
            definition.get("model") != settings.model
            or definition.get("instructions") != NAVIGATION_INSTRUCTIONS
            or definition.get("reasoning", {}).get("effort") != "low"
            or len(tools) != 1 or tools[0].get("type") != expected_type
            or (provider == "webiq" and tools[0].get("server_url") != "https://api.microsoft.ai/v3/mcp")
        ):
            raise ConfigError(f"{provider} does not match the shared profile. Prepare and pin the new agent versions.")
        snapshots[provider] = {
            "reference": reference.as_dict(), "model": definition["model"],
            "instructions_sha256": hashlib.sha256(definition["instructions"].encode()).hexdigest(),
            "tools_sha256": hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest(),
            "tool_types": [tool["type"] for tool in tools],
        }
    return snapshots


def compare(settings, prompt, context, repeats, out):
    for provider in PROVIDER_LABELS:
        settings.require(provider, voice=False)
        if not settings.agents[provider].version:
            raise ConfigError("Pin both TMAP_*_AGENT_VERSION values before a comparison.")
    from azure.ai.projects import AIProjectClient
    from tmap_poc.runtime import run_question
    from tmap_poc.voice import context_message

    at = datetime.now(timezone.utc).isoformat()
    message = context_message(context, at) + "\n\n사용자 질문:\n" + prompt
    manifest = {
        "schema_version": 1, "created_at": at,
        "kind": "text_development_comparison", "voice_executed": False,
        "model": settings.model, "repeats": repeats,
        "agents": {p: a.as_dict() for p, a in settings.agents.items()},
        "expected_instructions_sha256": hashlib.sha256(NAVIGATION_INSTRUCTIONS.encode()).hexdigest(),
        "input": message,
    }
    credential = settings.credential()
    try:
        with AIProjectClient(endpoint=settings.project_endpoint, credential=credential) as project:
            manifest["verified_profiles"] = verified_profiles(project, settings)
            out.mkdir(parents=True, exist_ok=False)
            _write(out / "manifest.json", manifest)
            client = project.get_openai_client().with_options(max_retries=0)
            with client, (out / "runs.jsonl").open("x", encoding="utf-8") as output:
                for repeat in range(1, repeats + 1):
                    order = list(PROVIDER_LABELS)
                    if repeat % 2 == 0:
                        order.reverse()
                    for provider in order:
                        agent = settings.agents[provider]
                        with span("experiment.trial"):
                            record = run_question(
                                client, {"name": agent.name, "version": agent.version},
                                settings.model, message, answer_format="text",
                            )
                            record["trace_id"] = trace_id()
                        record.update({
                            "provider": provider, "repeat": repeat, "input": message,
                            "transport": "foundry_responses", "voice_executed": False,
                        })
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")
                        output.flush()
                        os.fsync(output.fileno())
                        print(f"{provider} repeat={repeat} completed={record['completed']}")
            manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
            _write(out / "manifest.json", manifest)
    finally:
        close = getattr(credential, "close", None)
        if close is not None:
            close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Foundry voice agent and text experiments")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Serve the local voice interface")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    agents = commands.add_parser("prepare-agents", help="Plan/register shared voice-ready agents")
    agents.add_argument("--prefix", default="tmap-voice")
    agents.add_argument("--apply", action="store_true")
    experiment = commands.add_parser("compare", help="Run a paid text comparison when explicitly invoked")
    experiment.add_argument("--prompt", required=True)
    experiment.add_argument("--context", default="")
    experiment.add_argument("--repeats", type=int, default=1)
    experiment.add_argument("--out", type=Path, required=True)
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
        else:
            if args.repeats < 1 or not args.prompt.strip() or len(args.prompt) > 4000 or len(args.context) > 4000:
                parser.error("Use a nonempty prompt/context up to 4000 characters and positive repeats.")
            compare(settings, args.prompt, args.context, args.repeats, args.out)
    except ConfigError as exc:
        parser.error(str(exc))
    finally:
        shutdown_tracing()


if __name__ == "__main__":
    main()
