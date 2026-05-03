# Pre-show — shared setup for all demo runbooks

> One-time setup, ~1 hour before the talk. Each step is annotated with **(needed
> for: <demos>)** so you can skip what you don't plan to run.
>
> - **Core runbook** ([DEMO-RUNBOOK-CORE.md](DEMO-RUNBOOK-CORE.md)) — Demos 2, 5, 7.
> - **Full runbook** ([DEMO-RUNBOOK.md](DEMO-RUNBOOK.md)) — Demos 1–7.
>
> Resource names assume `AZURE_ENV_NAME=demo` in the eastus2 region. Substitute
> the values printed by `azd env get-values` after the first `azd up`.

## 1. Authenticate **(needed for: all demos)**

```bash
az login
azd auth login
```

## 2. Provision and deploy the full ACA stack **(needed for: 2, 3, 4, 5, 6, 7)**

The agent is part of `azd up`, no manual portal step needed. Demo 7 also pulls
ACR endpoint and Foundry values from this env later.

```bash
cd agentic-devops-demo
azd env new demo
azd env set AZURE_LOCATION eastus2
azd env set AZURE_AI_LOCATION eastus2
azd up
```

`azd up` runs Bicep (which creates the Foundry project, the
`clinical_trial_matcher` connection, and the model deployment) and then the
postdeploy hook runs `infra/scripts/sync_agent.py`, which reconciles
`.foundry/agent-metadata.yaml` into a new agent version. Confirm the frontend
URL works and chat returns a real agent response.

## 3. Pre-stage the GitHub issue **(needed for: 3, 4)**

UI: *Issues → New issue*. Leave it **unassigned**.

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

## 4. GitHub OIDC + repo secrets **(needed for: 4, 7)**

Confirm the GitHub OIDC federated credential exists and these are set as repo
secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

Both `deploy.yml` (Demo 4) and `aks-deploy.yml` (Demo 7) authenticate to Azure
through this federated identity.

## 5. Foundry / AI Toolkit VS Code extension **(needed for: 2)**

Open VS Code with the AI Toolkit / Microsoft Foundry extension installed and
logged into the same tenant.

## 6. Optional — warm Foundry **(needed for: 2, 4)**

Send one chat from your laptop using the frontend URL:

```bash
azd env get-values | grep FRONTEND_URL
```

## 7. Pre-stage the `/version` watch loop **(needed for: 4)**

The API normally has internal-only ingress, so flip it to external for the
recording, then run the watcher (curls `/version` every 5s and prints
`git_sha`):

```bash
./demo4-ingress-external.sh   # one-time flip; ~30s for LB to propagate
./demo4-version-watch.sh      # tails /version forever (Ctrl+C to stop)
```

Smoke-test it now — **before** Demo 3 merges the PR, the loop prints the
currently-deployed SHA (or `(no response)` if `/version` doesn't exist yet in
main). After Demo 4 deploys, the same loop starts printing the new SHA. That
contrast is the punchline. The script auto-resolves `AZURE_RESOURCE_GROUP` and
the API container app name from the current azd env — nothing to remember on
stage.

**After the recording**, restore internal ingress:

```bash
./demo4-ingress-internal.sh
```

## 8. Provision Azure SRE Agent **(needed for: 6)**

One-time, not in Bicep — it's a tenant-level resource, typically one per
team/subscription.

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

## 9. Provision the AKS cluster + KAITO + ingress **(needed for: 7)**

The AKS cluster is **not** part of `azd up`; the workflow at
[.github/workflows/aks-deploy.yml](../.github/workflows/aks-deploy.yml) only
runs `helm upgrade`, it does not create the cluster.

### 9.1 Create the cluster

Pull the user-assigned MI's resource id (created by `azd up`) and the RG:

```bash
eval "$(azd env get-values | grep -E '^(AZURE_RESOURCE_GROUP|AZURE_CLIENT_ID)=')"
MI_RESOURCE_ID=$(az identity list -g "$AZURE_RESOURCE_GROUP" \
  --query "[?clientId=='$AZURE_CLIENT_ID'].id | [0]" -o tsv)
```

Deploy the cluster Bicep (System-assigned identity, OIDC issuer, workload
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

### 9.2 Install KAITO and the Llama-3.2-3B Workspace

The watcher calls `http://workspace-llama-3-3b/v1/chat/completions` for every
score; without this step the Trial Watch tab will score everything as 0.

```bash
# KAITO controller (self-install, NOT via AKS AI add-on — gives us
# control over featureGates and lets us pin to CPU nodes).
git clone --depth=1 -b v0.10.0 https://github.com/kaito-project/kaito /tmp/kaito-src
helm install kaito-workspace /tmp/kaito-src/charts/kaito/workspace \
  --namespace kaito-workspace --create-namespace \
  --set featureGates.disableNodeAutoProvisioning=true \
  --set nvidiaDevicePlugin.enabled=false

# The sys nodepool VMSS is labeled apps=llama-3-3b at creation time
# (see aks/cluster.bicep / `az aks nodepool update --labels`), so the
# label survives reimage and we don't need to relabel by hand. Just
# create the Workspace CR — KAITO finds a matching node automatically.
kubectl apply -f aks/kaito/workspace-llama-3-3b.yaml
kubectl wait --for=condition=Ready workspace/workspace-llama-3-3b --timeout=15m
```

> **One-time bootstrap on a fresh cluster** (skip if the sys pool already
> carries `apps=llama-3-3b` — check with `kubectl get nodes --show-labels | grep apps=`):
>
> ```bash
> az aks nodepool update -g "$AZURE_RESOURCE_GROUP" --cluster-name "$AKS_NAME" \
>   -n sys --labels apps=llama-3-3b
> ```

### 9.3 Install an ingress controller

[aks/helm/templates/ingress.yaml](../aks/helm/templates/ingress.yaml) creates
an `Ingress` (class `nginx`) but the chart does **not** install the controller:

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.service.externalTrafficPolicy=Local
kubectl -n ingress-nginx get svc ingress-nginx-controller \
  -w   # wait for EXTERNAL-IP, then use nip.io / sslip.io
```

> **Why `externalTrafficPolicy=Local`?** With the default `Cluster` policy,
> the Azure LB health probe hits the controller's nodePort at `/`, gets a 404
> from nginx, and marks every backend unhealthy — so external traffic times
> out even though pods are Running. `Local` makes AKS provision a dedicated
> `/healthz` probe (and preserves client source IPs as a bonus). If you forget
> this on a fresh install, patch the running Service:
>
> ```bash
> kubectl -n ingress-nginx patch svc ingress-nginx-controller \
>   -p '{"spec":{"externalTrafficPolicy":"Local"}}'
> ```

### 9.4 Set GitHub repo Variables for `aks-deploy.yml`

Settings → Secrets and variables → Actions → Variables:

- `AKS_RESOURCE_GROUP` = `$AZURE_RESOURCE_GROUP`
- `AKS_CLUSTER_NAME` = the `$AKS_NAME` from step 9.1
- `ACR_LOGIN_SERVER` = `AZURE_CONTAINER_REGISTRY_ENDPOINT` from `azd env get-values`
- `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_FOUNDRY_AGENT_NAME`,
  `AZURE_AI_MODEL_DEPLOYMENT` — all from `azd env get-values`
- `AKS_WORKLOAD_IDENTITY_CLIENT_ID` = `AZURE_CLIENT_ID`
- `INGRESS_HOST` = your DNS name (e.g. `trial-matcher.<lb-ip>.sslip.io`)
- Secret `APPLICATIONINSIGHTS_CONNECTION_STRING` (from the App Insights
  resource created by `azd up`).

### 9.5 Smoke-test the AKS deploy

Manually trigger `aks-deploy.yml` once before the talk so images are pulled
and pods are warm.
