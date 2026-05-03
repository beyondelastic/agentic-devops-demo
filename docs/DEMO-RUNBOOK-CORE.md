# Demo runbook (core) — Demos 2, 5, 7

> Slim presenter script focused on the three demos that show off the
> "agent-as-code → ACA scale → AKS-shaped workload" arc. Demos 1, 3, 4, 6 are
> documented in the [full runbook](DEMO-RUNBOOK.md) and treated as optional
> here.

## Before you start

Run through [PRE-SHOW.md](PRE-SHOW.md). For this slim runbook you need:

| Pre-show step | Why |
|---|---|
| 1. Authenticate | all demos |
| 2. `azd up` (ACA stack) | Demo 2 + Demo 5 |
| 4. GitHub OIDC + repo secrets | Demo 7's `aks-deploy.yml` |
| 5. Foundry / AI Toolkit VS Code extension | Demo 2 |
| 6. *(Optional)* Warm Foundry | Demo 2 |
| 9. AKS cluster + KAITO + ingress + repo Variables | Demo 7 |

You can skip pre-show steps 3, 7, 8 (they're for the optional Demos 3, 4, 6).

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

4. **Live edit → PR → CI → new agent version (the punchline).** Kick this off
   *first*, then narrate steps 1–3 while CI runs. Goal: same question to the
   running app produces visibly different behaviour by the end of the demo,
   triggered only by a Git diff.

   1. In a terminal, before going on stage, set the patient query you'll use
      twice. Pick one and say it out loud both times for the audience:
      > *"Find a stage 2 lung cancer trial."*

      With today's prompt the agent asks for age/sex/location first. That's the
      "before."
   2. Open [.foundry/prompts/system.md](../.foundry/prompts/system.md) and make
      two paste-in-place edits.

      **Edit A — search-first behaviour.** Find the line that starts with
      `1. The user provides a free-text patient description...` and **replace
      that single numbered item** with this block (keeps numbering intact):

      ~~~markdown
      1. The user provides a free-text patient description plus structured fields (age, sex,
         primary condition, optional location).
         - If the user provides only a condition, call `search_trials` immediately with
         sensible defaults (limit=3) and present matches first.
         - Ask follow-up questions about age/sex/location *after* showing the initial
         results, to refine.
      ~~~

      **Edit B — clinical disclaimer.** In the `## Style and safety` section,
      find the line `- Be concise. Lists, not paragraphs.` and **add this new
      bullet directly under it**:

      ~~~markdown
      - When you mention a specific trial, end the response with a single-line italic disclaimer: *Informational only — eligibility must be confirmed by the trial site.*
      ~~~
   3. **Reconcile the change into Foundry (~5s).** This calls the *same*
      [infra/scripts/sync_agent.py](../infra/scripts/sync_agent.py) that the
      `azd postdeploy` hook runs in CI — just locally and without waiting on
      the pipeline. First run takes ~20s while it builds a venv; subsequent
      runs are ~5s.
      ```bash
      ./demo2-sync.sh
      ```
      Watch for the final line: `Created agent version: name=clinical-trial-matcher version=N`.

   4. Refresh the agent in the Foundry/AI Toolkit extension — the version list
      ticks up by one. Ask the running app the *same* question again. The
      answer now goes straight to trial cards and ends with the disclaimer.
      **No portal clicks.**

   *(Stage line as the new behaviour appears: "Two product asks — 'don't gate
   answers behind demographics' and 'add a clinical disclaimer.' In a portal,
   that's a meeting and a ticket. Here, it's a PR.")*

   5. **Optional — close the GitOps loop after the live demo.** Commit the
      same file change, push, merge. CI re-runs `sync_agent.py`, producing
      one more version. You don't need this on stage; it's the proof point
      for "the local script and the CI pipeline run identical code."
      ```bash
      git checkout -b demo2-prompt-update
      git add .foundry/prompts/system.md
      git commit -m "agent: search-first behaviour + clinical disclaimer"
      git push -u origin demo2-prompt-update
      gh pr create --fill --base main && gh pr merge --squash --auto
      ```

5. Make the limitation explicit, then turn it into the punchline:

   > "The extension can't *author* the OpenAPI tool wiring — there's no picker for
   > it today. That's fine. **I don't want my agents authored in a UI anyway.**
   > Every PR merge runs the same `sync_agent.py` in GitHub Actions —
   > the agent gets the same pipeline as the rest of the app."

**Narrative beat:** "Low-code is great for exploration. Production demands a Git
SHA, a pipeline, and a reproducible deploy. The agent gets the same treatment as
the API container."

---

## Demo 5 — ACA scales under load (≈4 min)

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

## Demo 7 — Trial Watch on AKS: in-cluster model + stateful watcher (≈4 min)

> **One-line pitch:** "ACA gave us request/response. AKS gives us a long-running,
> stateful inference loop with an in-cluster open-source model — that's the
> AKS-shaped workload."

### What's actually running

| Component | Where | Why on AKS |
| --- | --- | --- |
| `frontend` (nginx + React) | Deployment, 2 replicas | identical to ACA |
| `api` (FastAPI) | Deployment, HPA 2→20 | adds `/api/watches/*` and `/api/trials` |
| `redis` (single replica, no PVC) | Deployment | shared state for watches + results |
| `watcher` (FastAPI loop) | Deployment | ticks every 45s — **the long-running workload** |
| `tools` (FastAPI search) | Deployment, 1 replica | in-memory trial dataset for the demo |
| `workspace-llama-3-3b` | KAITO Workspace, CPU node `apps=llama-3-3b` | **Llama-3.2-3B Instruct** (Q4_K_M GGUF via aikit/llama.cpp), OpenAI-compatible `/v1` |

Flow: `POST /api/watches` → Redis → watcher tick reads watches → `tools` search → in-cluster Llama scores each trial → results back to Redis → `GET /api/watches/stream` (SSE) pushes updates to UI.

### On-stage script

1. **Open the AKS ingress** (`http://<lb-ip>.nip.io/`) → click the **🔭 Trial Watch** tab.
   You'll see three seeded watches (Aunt Helen NSCLC, Patient B melanoma, cohort screening) with score badges, tier labels, and a green "live" pill — that's the SSE stream.
2. **Show what makes this AKS-shaped** — flip to a terminal:
   ```bash
   kubectl -n trial-matcher get pods -l app=watcher
   kubectl -n trial-matcher logs deploy/watcher --tail=20
   ```
   Point at the lines:
   ```
   watcher tick start watches=3
   HTTP Request: POST http://tools:8000/tools/search_trials "200 OK"
   HTTP Request: POST http://workspace-llama-3-3b/v1/chat/completions "200 OK"
   match watch=demo-w1 trial=TM-2025-001 score=60 prev=60 new=False
   ```
   "Every 45 seconds, in-cluster. No Foundry call here — that's our open-source Llama running on a CPU node next door."
3. **Inject a fresh trial live.** Back in the UI, click **`+ Import trial`** → **`fill with NSCLC example`** → **Add trial**.
   A toast appears: *Added trial TM-DEMO-XXXXXX — next watcher tick will pick it up and emit a NEW pill.*
4. **Wait one tick (~45s).** The Aunt Helen card should:
   - flash an indigo pulse border (recent-update animation),
   - gain a `1 NEW` aggregate badge in the header,
   - show the new trial result with a `NEW` pill and an emerald score badge (**≈80–100, "Strong match"** — the watcher pre-computes age/sex/location verdicts in Python and feeds them to the 3B model as ground truth, then floors the score at 80 when every hard check passes).
   If the score later changes on a subsequent tick, a `▲N` / `▼N` delta badge appears.
5. **Closing line:** "Same containers, same pipeline, same agent — plus a stateful inference loop and an open-source model that lives inside the cluster. ACA for the fastest path. AKS when you need the ceiling."

### If something goes sideways

| Symptom | Fix |
| --- | --- |
| `+ Import trial` returns 502 | `kubectl -n trial-matcher rollout restart deploy/tools` (single-worker; pod must be healthy) |
| Tick runs but no NEW pill | Check `kubectl logs deploy/watcher` — confirm `trials_found` increased; the new trial id only matches when the watch's search terms hit the title/condition |
| SSE pill says "stalled" | `kubectl -n trial-matcher rollout restart deploy/api` |
| Llama 5xx | `kubectl get workspace workspace-llama-3-3b` — must be `Ready`; the GGUF runtime is single-replica on the labeled node |

### Reset Trial Watch state between rehearsals

```bash
# Drop watch results + injected trials; restart watcher and tools:
kubectl -n trial-matcher exec deploy/redis -- redis-cli FLUSHDB
kubectl -n trial-matcher rollout restart deploy/watcher deploy/tools
```
The three demo seeds (`demo-w1/w2/w3`) are re-created by the watcher on next start.

---

## Reset between rehearsals

```bash
# Clean teardown of the ACA stack (keeps AKS untouched):
azd down --purge --force
```

For Demo 7, use the Trial Watch reset block above instead of full teardown
between back-to-back rehearsals.
