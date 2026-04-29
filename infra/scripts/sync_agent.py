#!/usr/bin/env python3
"""Upsert the Foundry prompt agent from `.foundry/agent-metadata.yaml`.

Runs as an azd `postdeploy` hook (and from the GitHub Actions deploy workflow)
once Bicep has provisioned the Foundry project + model deployment. Uses the
current Foundry SDK (`azure-ai-projects` `AIProjectClient`).

The agent is recreated as a new version every run, idempotently.

Required env vars (provided by `azd env get-values` after `azd provision`):

* AZURE_AI_PROJECT_ENDPOINT
* AZURE_AI_MODEL_DEPLOYMENT
* AZURE_FOUNDRY_AGENT_NAME
* TOOLS_OPENAPI_URL                # OpenAPI spec the agent calls as a tool

Skipped silently if `.foundry/agent-metadata.yaml` is missing — useful before
Demo 2 has happened.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sync_agent")

ROOT = Path(__file__).resolve().parents[2]
META_PATH = ROOT / ".foundry" / "agent-metadata.yaml"


def _required(var: str) -> str:
    val = os.environ.get(var)
    if not val:
        log.error("Required env var %s is missing", var)
        sys.exit(2)
    return val


def main() -> int:
    if not META_PATH.exists():
        log.warning(
            "%s not found — skipping agent sync. (Expected before Demo 2 has been performed.)",
            META_PATH.relative_to(ROOT),
        )
        return 0

    # Imports deferred so pre-Demo-2 deploys don't pay the SDK cost or fail
    # if the SDK shape drifts (this script is only exercised once metadata exists).
    import yaml
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        OpenApiAnonymousAuthDetails,
        OpenApiFunctionDefinition,
        OpenApiProjectConnectionAuthDetails,
        OpenApiProjectConnectionSecurityScheme,
        OpenApiTool,
        PromptAgentDefinition,
    )
    from azure.identity import DefaultAzureCredential

    endpoint = _required("AZURE_AI_PROJECT_ENDPOINT")
    model = _required("AZURE_AI_MODEL_DEPLOYMENT")
    agent_name = os.environ.get("AZURE_FOUNDRY_AGENT_NAME", "clinical-trial-matcher")
    tools_openapi_url = os.environ.get("TOOLS_OPENAPI_URL", "")
    tools_connection_name = os.environ.get(
        "AZURE_FOUNDRY_TOOLS_CONNECTION_NAME", "clinical_trial_matcher"
    )

    meta = yaml.safe_load(META_PATH.read_text(encoding="utf-8"))
    instructions = _resolve_instructions(meta)

    log.info("Connecting to Foundry project: %s", endpoint)
    client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    tools = []
    if tools_openapi_url:
        spec = _fetch_openapi_spec(tools_openapi_url)
        if spec is not None:
            auth = _resolve_tool_auth(client, tools_connection_name)
            tools.append(
                OpenApiTool(
                    openapi=OpenApiFunctionDefinition(
                        name="trial_tools",
                        description=(
                            "Search clinical trials, check patient eligibility, "
                            "summarize trials."
                        ),
                        spec=spec,
                        auth=auth,
                    )
                )
            )
            log.info("Registered OpenAPI tool 'trial_tools' from %s", tools_openapi_url)
        else:
            log.warning("Could not fetch OpenAPI spec — agent will be created without tools")

    definition = PromptAgentDefinition(
        model=model,
        instructions=instructions,
        tools=tools,
    )

    log.info("Upserting declarative agent '%s' (new version)", agent_name)
    version = client.agents.create_version(
        agent_name=agent_name,
        definition=definition,
    )
    log.info(
        "Created agent version: name=%s version=%s",
        getattr(version, "name", agent_name),
        getattr(version, "version", "?"),
    )
    return 0


def _resolve_tool_auth(client, connection_name: str):
    """Resolve the OpenAPI tool auth.

    Prefers a project connection (so the Foundry runtime injects the configured
    `x-api-key` header into tool calls). Falls back to anonymous if the named
    connection is not present in the project.
    """
    from azure.ai.projects.models import (
        OpenApiAnonymousAuthDetails,
        OpenApiProjectConnectionAuthDetails,
        OpenApiProjectConnectionSecurityScheme,
    )

    if not connection_name:
        return OpenApiAnonymousAuthDetails()
    try:
        conn = client.connections.get(name=connection_name)
    except Exception as e:  # noqa: BLE001
        log.warning(
            "Project connection %r not found (%s) — falling back to anonymous auth. "
            "Tool calls will fail if the tools service requires an x-api-key header.",
            connection_name,
            e,
        )
        return OpenApiAnonymousAuthDetails()
    log.info("Using project connection %r (%s) for OpenAPI tool auth", conn.name, conn.id)
    return OpenApiProjectConnectionAuthDetails(
        security_scheme=OpenApiProjectConnectionSecurityScheme(
            project_connection_id=conn.id,
        ),
    )


def _resolve_instructions(meta: dict) -> str:
    """Pull instructions out of agent-metadata.yaml.

    Supports either inline `instructions:` or a `instructions_file:` reference.
    """
    if "instructions" in meta and meta["instructions"]:
        return str(meta["instructions"]).strip()
    if "instructions_file" in meta:
        path = (META_PATH.parent / meta["instructions_file"]).resolve()
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    log.warning("No instructions found in agent-metadata.yaml; using minimal fallback.")
    return "You are a helpful clinical-trial-matching assistant for a demo."


def _fetch_openapi_spec(url: str):
    """Fetch the OpenAPI spec the tools service publishes at /openapi.json."""
    try:
        import json
        import urllib.request

        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 - internal URL
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("Failed to fetch OpenAPI spec from %s: %s", url, e)
        return None


if __name__ == "__main__":
    raise SystemExit(main())
