# Demo runbook — "Powering AI Apps and Agents at Scale with Azure App Platform"

> Copy/paste-ready presenter script. Resource names assume `AZURE_ENV_NAME=demo`
> in the eastus2 region. Substitute the values printed by `azd env get-values`
> after the first `azd up`.

## Pre-show (do this once, ~1 hour before the talk)

1. Authenticate.
   ```bash
   az login
   azd auth login
   ```
2. Provision and deploy the **full** stack — the agent is part of `azd up`, no manual portal step needed.
   ```bash
   cd agentic-devops-demo
   azd env new demo
   azd env set AZURE_LOCATION eastus2
   azd env set AZURE_AI_LOCATION eastus2
   azd up
   ```
   `azd up` runs Bicep (which creates the Foundry project, the `clinical_trial_matcher`
   connection, and the model deployment) and then the postdeploy hook runs
   `infra/scripts/sync_agent.py`, which reconciles `.foundry/agent-metadata.yaml`
   into a new agent version. Confirm the frontend URL works and chat returns a
   real agent response.
3. Pre-stage a GitHub issue in the repo (UI: *Issues → New issue*). Leave it **unassigned**.

   **Title**
   ```
   Add /version endpoint to API
   ```

   **Body** (paste verbatim, Markdown):
   ```markdown
   The API container already receives `GIT_SHA` and `BUILT_AT` as build args
   (see `apps/api/Dockerfile`) and exposes them as environment variables, but
   nothing in the running app surfaces them. Add a small read-only endpoint so
   operators can confirm what's deployed.

   ### Acceptance criteria
   - [ ] `GET /version` in `apps/api/src/api/main.py` returns JSON
         `{ "git_sha": "<env GIT_SHA>", "built_at": "<env BUILT_AT>" }`.
   - [ ] Both fields fall back to the string `"unknown"` if the env var is unset.
   - [ ] No auth required — same posture as `/healthz`.
   - [ ] Add a pytest under `apps/api/tests/` using FastAPI's `TestClient` that
         asserts the response shape and status 200.
   - [ ] No changes outside `apps/api/`.

   ### Out of scope
   - Frontend changes.
   - Bicep / infra changes.
   - Logging or telemetry hooks.
   ```
4. Confirm GitHub OIDC federated credential exists and `AZURE_CLIENT_ID`,
   `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` are set as repo secrets.
5. Open VS Code with the AI Toolkit / Microsoft Foundry extension installed and
   logged into the same tenant.
6. Optional: warm Foundry by sending one chat from your laptop using
   `azd env get-values | grep FRONTEND_URL`.
7. Provision **Azure SRE Agent** for Demo 6 (one-time, not in Bicep — it's a
   tenant-level resource, typically one per team/subscription).
   - Portal → *Create a resource* → search **Azure SRE Agent** → create in the
     same subscription as `rg-<env>-agentic-devops`.
   - In the agent's *Access* / *Scope* blade, grant it **Reader** +
     **Monitoring Reader** on the resource group so it can read Container Apps
     revisions, logs, metrics, and Activity Log (which is how it correlates the
     `ENABLE_MEMORY_LEAK=true` env-var change to the OOM restart loop).
   - Smoke-test: ask it *"what's running in this resource group?"* — confirm it
     sees `adgd-api-<token>` before you go on stage.
   - Optional: install the SRE Agent's GitHub App on this repo if you want the
     "open a remediation PR" beat. Not required for the core Demo 6 narrative.
8. *(Optional — only if running Demo 7)* Provision the AKS cluster. It is
   **not** part of `azd up`; the workflow at
   [.github/workflows/aks-deploy.yml](../.github/workflows/aks-deploy.yml)
   only runs `helm upgrade`, it does not create the cluster.

   1. Pull the user-assigned MI's resource id (created by `azd up`) and the RG:
      ```bash
      eval "$(azd env get-values | grep -E '^(AZURE_RESOURCE_GROUP|AZURE_CLIENT_ID)=')"
      MI_RESOURCE_ID=$(az identity list -g "$AZURE_RESOURCE_GROUP" \
        --query "[?clientId=='$AZURE_CLIENT_ID'].id | [0]" -o tsv)
      ```
   2. Deploy the cluster Bicep (System-assigned identity, OIDC issuer, workload
      identity, federated to `system:serviceaccount:trial-matcher:trial-matcher`):
      ```bash
      AKS_NAME="adgd-aks-$(azd env get-values | awk -F= '/AZURE_RESOURCE_GROUP/{gsub(/"/,""); print $2}' | awk -F- '{print $NF}')"
      az deployment group create \
        -g "$AZURE_RESOURCE_GROUP" \
        -f aks/cluster.bicep \
        -p clusterName="$AKS_NAME" \
           workloadIdentityResourceId="$MI_RESOURCE_ID"
      az aks get-credentials -g "$AZURE_RESOURCE_GROUP" -n "$AKS_NAME" --overwrite-existing
      ```
   3. Install an ingress controller — `aks/helm/templates/ingress.yaml` creates
      an `Ingress` (class `nginx`) but the chart does **not** install the
      controller:
      ```bash
      helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
      helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
        --namespace ingress-nginx --create-namespace \
        --set controller.service.type=LoadBalancer
      kubectl -n ingress-nginx get svc ingress-nginx-controller \
        -w   # wait for EXTERNAL-IP, then point DNS / use sslip.io
      ```
   4. Set the GitHub repo **Variables** (Settings → Secrets and variables →
      Actions → Variables) consumed by `aks-deploy.yml`:
      - `AKS_RESOURCE_GROUP` = `$AZURE_RESOURCE_GROUP`
      - `AKS_CLUSTER_NAME` = the `$AKS_NAME` from step 8.2
      - `ACR_LOGIN_SERVER` = `AZURE_CONTAINER_REGISTRY_ENDPOINT` from `azd env get-values`
      - `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_FOUNDRY_AGENT_NAME`,
        `AZURE_AI_MODEL_DEPLOYMENT` — all from `azd env get-values`
      - `AKS_WORKLOAD_IDENTITY_CLIENT_ID` = `AZURE_CLIENT_ID`
      - `INGRESS_HOST` = your DNS name (e.g. `trial-matcher.<lb-ip>.sslip.io`)
      - Secret `APPLICATIONINSIGHTS_CONNECTION_STRING` (from the App Insights
        resource created by `azd up`).
   5. Smoke-test by manually triggering the workflow once before the talk so
      images are pulled and pods are warm.

---

## Demo 1 — GitHub Copilot (VS Code, agent mode) generates `lint.yml` (≈2 min)

1. In VS Code, open the Copilot Chat side panel and switch the mode dropdown
   to **Agent**. Confirm the workspace is `agentic-devops-demo` so the agent
   can read/write files directly.
2. Send this prompt:
   ```
   Create a GitHub Actions workflow at .github/workflows/lint.yml that runs ruff
   on apps/api and apps/tools on PRs to main. Use Python 3.12, matrix over the
   two services, and pip install -e .[dev] inside each service directory.
   ```
3. Watch the agent create `.github/workflows/lint.yml` in the editor. Accept
   the change, then commit and push from the integrated terminal:
   ```bash
   git add .github/workflows/lint.yml
   git commit -m "ci: add lint workflow"
   git push
   ```
4. Open the PR check tab on GitHub — green.

**Why this is safe:** purely additive; nothing else depends on this workflow.
**Why agent mode (not chat):** zero copy/paste — the agent writes the file,
runs the commit, and you narrate. Faster on stage and shows off the newer
Copilot UX.

---

## Demo 2 — The agent is code, not clicks (≈3 min)

> **Framing:** "I'm not going to build an agent in a portal — that's not the point of
> this talk. The point is: when an agent goes to production, it has to live in the
> same place every other piece of your system lives — in Git, behind a pipeline."

1. Open the Foundry / AI Toolkit VS Code extension. Connect to the project
   provisioned by `azd up`. Show:
   - The `gpt-4o-mini` model deployment (from Bicep).
   - The `clinical-trial-matcher` agent already exists, with versions.

   *(Beat: "I never opened a portal. This came from `azd up`.")*

2. Open three files side-by-side and walk them top-down:

   | File | What it owns |
   |---|---|
   | [.foundry/agent-metadata.yaml](../.foundry/agent-metadata.yaml) | Declarative agent: name, model, instructions file, OpenAPI tool. |
   | [infra/modules/foundry-connection.bicep](../infra/modules/foundry-connection.bicep) | The `clinical_trial_matcher` project connection that injects `x-api-key` on every tool call. |
   | [infra/scripts/sync_agent.py](../infra/scripts/sync_agent.py) | Reconciles the YAML into Foundry via `AIProjectClient.agents.create_version`, binding the connection as the OpenAPI auth. Runs as the `azd` postdeploy hook. |

3. *(Optional 30s beat — only if it lands)* In the extension, expand the agent's
   versions list. Point at the latest version's tool definition — read-only, but
   it proves the YAML actually shaped what's running.

4. Make the limitation explicit, then turn it into the punchline:

   > "The extension can't *author* the OpenAPI tool wiring — there's no picker for
   > it today. That's fine. **I don't want my agents authored in a UI anyway.**
   > Demo 4 will show this YAML get reconciled by GitHub Actions on every PR
   > merge — same pipeline as the rest of the app."

**Narrative beat:** "Low-code is great for exploration. Production demands a Git
SHA, a pipeline, and a reproducible deploy. The agent gets the same treatment as
the API container."

---

## Demo 3 — GitHub Coding Agent fixes the `/version` issue (≈3 min)

1. Open the pre-staged issue. Assign to **Copilot**.
2. Switch to a different slide while the agent works (~2–3 min).
3. Return; review the PR; merge.

---

## Demo 4 — GitHub Actions deploys to Azure Container Apps (≈3 min)

The merge in Demo 3 triggered `deploy.yml`. While it runs:

1. Open the Actions tab. Walk through the steps:
   - OIDC login (no secrets, federated credential).
   - `azd up` (idempotent — Bicep is a no-op on already-provisioned resources).
   - **Postdeploy hook** runs `infra/scripts/sync_agent.py` which calls
     `AIProjectClient.agents.create_version` to upsert the agent from the
     committed `.foundry/agent-metadata.yaml`.
2. When green, hit the frontend URL. Send a real chat — agent responds via Foundry.
3. Show the new `/version` endpoint:
   ```bash
   curl https://<api-fqdn>/version
   ```
   *(The API ingress is internal — proxy through the frontend or use `az containerapp exec`.)*

---

## Demo 5 (optional) — ACA scales under load (≈4 min)

1. Show current replicas:
   ```bash
   az containerapp replica list -g <rg> -n adgd-api-<token> -o table
   ```
2. Run k6 from your laptop (wraps the `FRONTEND_URL` lookup + `k6 run`):
   ```bash
   ./load.sh
   ```
3. Re-run `replica list` every 30s. Watch count grow → 10 → settle back to 1.
4. Show the Container App **Metrics** blade: Replica Count + Requests.

---

## Demo 6 — Azure SRE Agent diagnoses a memory leak (≈6 min)

> **Why pre-stage terminals?** ACA auto-replaces OOM'd replicas, so the portal's
> *Replicas* blade almost always shows N/N healthy — there's no `RESTARTS`
> counter like `kubectl get pods`. Pre-stage these so the failure is *visible*.

### Pre-stage terminals (open before the demo, split-screen on stage)

Substitute `<rg>`, `<api>`, and `<rev>` with the values from `azd env get-values`
(e.g. `rg-aullah-agentic-devops`, `adgd-api-3wnyg3nk2w76m`,
`adgd-api-3wnyg3nk2w76m--0000003`).

> All four shell scripts auto-resolve `RG` / `API_NAME` / `FRONTEND_URL` from
> `azd env get-values` via [demo6-env.sh](../demo6-env.sh) — no copy/pasting
> resource names mid-demo.

1. **Replica churn** — names rotate and `created` timestamps reset on every
   OOMKill, even though the count stays at N/N. In its own pane:
   ```bash
   ./demo6-watch.sh
   ```
2. **System log stream** — the crispest "things are dying" signal; you'll see
   `OOMKilled` and `Replica … has been provisioned` lines scroll by. In its own
   pane:
   ```bash
   ./demo6-logs.sh
   ```
3. **Container App → Metrics blade** — pin three on one chart, last 30 min:
   - **Replica Restart Count** (step-increments on every OOMKill — the money
     graph for the audience)
   - **Memory Working Set Bytes**, split by Replica (sawtooth = leak + restart)
   - **Replica Count**
4. *(Optional)* **Log Analytics → Logs blade**, pre-loaded with this query so
   you can hit *Run* live:
   ```kusto
   ContainerAppSystemLogs_CL
   | where ContainerAppName_s == "<api>"
   | where TimeGenerated > ago(15m)
   | where Reason_s in ("OOMKilled", "BackOff", "Unhealthy", "Killing")
   | project TimeGenerated, ReplicaName_s, Reason_s, Log_s
   | order by TimeGenerated desc
   ```

### Demo flow

1. **Kick off the leak scenario** — caps `--max-replicas 2`, sets
   `ENABLE_MEMORY_LEAK=true`, then runs `k6 run load/k6-leak.js` for 10 min:
   ```bash
   ./demo6.sh
   ```
   Within 1–2 min the pre-staged terminals (`./demo6-watch.sh` and
   `./demo6-logs.sh`) will start showing OOMKills, replica churn, and the
   Replica Restart Count metric stepping up.
2. After ~3 min, show the unhealthy revision:
   ```bash
   az containerapp revision show -g <rg> -n adgd-api-<token> --revision <rev> -o jsonc
   ```
3. Open **Azure SRE Agent** scoped to the resource group. Ask it to investigate
   the API container app. It should surface:
   - Restart loop on the API revision.
   - Memory growth pattern (the `[demo-leak] buffer holds N chunks` warnings).
   - Correlated env-var change (`ENABLE_MEMORY_LEAK=true`).
   - Recommend rolling back the env var.
4. **Apply the fix** — disables the leak and restores `--max-replicas 5`:
   ```bash
   ./demo6-fix.sh
   ```
5. Watch healthy replicas come back up in the `./demo6-watch.sh` pane.

---

## Demo 7 (optional) — Same stack on AKS (≈3 min)

1. Trigger:
   - GitHub Actions → `aks-deploy` → **Run workflow**.
2. While it runs, show `aks/helm/templates/` — same three Deployments + Services + Ingress.
3. After deploy:
   ```bash
   kubectl --context <aks-ctx> get pods,svc,ingress -n trial-matcher
   ```
4. Hit the AKS ingress URL — same UX, different runtime.

**Closing line:** "ACA for the fastest path. AKS when you need the ceiling. The same containers, the same pipeline, the same agent."

---

## Reset between rehearsals

```bash
# Disable the leak and restore max-replicas in one shot:
./demo6-fix.sh

# Clean teardown:
azd down --purge --force
```
