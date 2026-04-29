# Powering AI Apps and Agents at Scale with Azure App Platform

A demo app showcasing the **agentic DevOps** story of GitHub + Microsoft. A clinical-trial-matcher app
written in Python, deployed to Azure Container Apps, with a Microsoft Foundry **prompt agent** doing
the inferencing and tool-calling. Same stack also ports to AKS.

> **Disclaimer:** All trial data in `data/synthetic_trials.json` is **synthetic** and for demonstration
> purposes only. This app is not intended for real clinical use, contains no PHI, and is not a
> medical device.

## Architecture

```
┌────────────┐    /api/*    ┌──────────────────┐   AIProjectClient   ┌───────────────────────┐
│  React UI  │ ───────────▶ │  FastAPI API     │ ──────────────────▶ │  Foundry prompt agent │
│  (nginx)   │              │  orchestrator    │                     │  (gpt-4o-mini)        │
└────────────┘              └──────────────────┘                     └─────────┬─────────────┘
       ▲                                                                       │ OpenAPI tool
       │ ACA internal DNS                                                      ▼
       │                                                              ┌───────────────────────┐
       │                                                              │  FastAPI tools server │
       └──────────────────────────────────────────────────────────────│  (search/eligibility) │
                                                                      └───────────────────────┘
```

Three Azure Container Apps, one user-assigned managed identity, one Foundry project, one model
deployment, one declarative agent committed in `.foundry/agent-metadata.yaml`.

## The seven demo beats

See [docs/DEMO-RUNBOOK.md](docs/DEMO-RUNBOOK.md) for the presenter script.

| # | Beat | What gets shown |
|---|------|-----------------|
| 1 | GitHub Copilot | Generate `.github/workflows/lint.yml` live with Copilot Chat |
| 2 | Foundry VS Code extension | Deploy model + author agent → export `.foundry/agent-metadata.yaml` |
| 3 | GitHub Coding Agent | Assign issue "Add `/version` endpoint" → review/merge PR |
| 4 | GH Actions → Azure Container Apps | Merge triggers OIDC → `azd deploy` → live URL |
| 5 (opt) | ACA scale | `k6 run load/k6-spike.js` → replicas scale 1 → 10 |
| 6 | Azure SRE Agent | Toggle `ENABLE_MEMORY_LEAK=true` → OOMs → SRE Agent RCA → revert |
| 7 (opt) | AKS port | `workflow_dispatch` deploys same images via Helm |

## Repo layout

```
agentic-devops-demo/
├── apps/
│   ├── frontend/   # React + Vite + nginx
│   ├── api/        # FastAPI orchestrator → Foundry
│   └── tools/      # FastAPI tools server (OpenAPI tool for the agent)
├── infra/
│   ├── main.bicep
│   ├── modules/
│   └── scripts/sync_agent.py    # Upserts agent from .foundry/agent-metadata.yaml
├── .foundry/
│   └── agent-metadata.yaml      # Foundry workspace standard (added live in Demo 2)
├── .github/workflows/
│   ├── deploy.yml               # OIDC → azd up
│   └── build.yml
├── data/synthetic_trials.json
├── load/k6-spike.js
├── aks/                         # Optional Demo 7
├── docs/DEMO-RUNBOOK.md
├── docker-compose.yml           # Local dev w/ FOUNDRY_MODE=mock
└── azure.yaml                   # azd service map
```

## Local development (mock Foundry)

```bash
cd agentic-devops-demo
cp .env.example .env
docker compose up --build
# open http://localhost:8080
```

With `FOUNDRY_MODE=mock` the API returns deterministic trial matches without calling Azure.

## Deploy to Azure

```bash
azd auth login
azd up
```

This provisions Foundry, ACR, Log Analytics, App Insights, the Container Apps env, three apps, role
assignments, and the model deployment, then runs `infra/scripts/sync_agent.py` to upsert the agent
from `.foundry/agent-metadata.yaml`.

## SDKs / versions

- `azure-ai-projects` (current Foundry entry-point — `AIProjectClient`)
- `azure-ai-agents` (data models for `PromptAgentDefinition`, tool definitions)
- `azure-identity` (`DefaultAzureCredential` — managed identity in Azure)
- `openai` (Responses API — streaming via `agent_reference`)
- Python 3.12, Node 20, Bicep, azd, ACA, AKS 1.30+

## License

MIT — see [LICENSE](LICENSE).
