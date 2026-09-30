# Error Budget Watcher

Error Budget Watcher builds on the NorthStar Retail Azure Digital Twin. It adds
an SRE reliability layer that turns the existing live metrics and fault scenarios
into an SLO view: current availability, remaining error budget, burn rate, breach
forecast, and a policy decision about whether to keep watching or start incident
response.

## How it works

```text
Live metrics → SLO and error-budget policy → risk forecast → recommendation
                                                                                 ↓ HIGH risk
                                  Existing Foundry agents → HITL approval → ServiceNow
```

The monthly availability target is 99.9%, equivalent to 43.2 minutes of error
budget in a 30-day window. Budget consumption and forecasts are deterministic
backend calculations. The watcher uses the sampler's retained history (15
minutes by default); this is a repeatable demo signal, not a claim of a full
30-day production SLI history. A HIGH-risk fault starts the existing seven-agent
incident workflow. Fix and ticket approvals remain human-controlled, and a real
ServiceNow ticket requires configured credentials.

## Run locally on Windows

Prerequisites: Python 3.12+, Node.js 20+, and (for the full agent/ticket flow)
Azure CLI authentication plus Azure AI Foundry and ServiceNow configuration.

1. Create the environment and install backend dependencies:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

2. Seed the NorthStar simulation. This resets the local simulation database:

```powershell
.venv\Scripts\python.exe backend\seed.py --mode normal
```

3. Copy `.env.example` to `.env` and configure the Foundry endpoint/agent names
    and ServiceNow connection. Authenticate Foundry with:

```powershell
az login --scope https://ai.azure.com/.default
```

4. Start the backend in one terminal:

```powershell
.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --port 8000
```

5. Start the dashboard in another terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open the Vite URL printed by the frontend (normally `http://localhost:5173`).
The dashboard and deterministic watcher work locally; Foundry and ServiceNow
configuration is needed to complete the external agent/ticket workflow.

## Demo flow

- Start from the seeded baseline and review availability, the budget bar, burn
   rate, and recommendation on the dashboard.
- Inject one of the five existing NorthStar faults. The watcher evaluates the
   affected resource; HIGH risk starts the incident workflow, while lower risk
   remains in monitoring.
- Follow the agent canvas and event log on **Orchestration**. Approve the
   recommended fix and ticket through the existing HITL controls.
- Restore the normal sampler profile before replaying a scenario.

The frontend production/typecheck gate is `cd frontend; npm.cmd run build`.
The backend health endpoint is `http://localhost:8000/api/health`.
