# NorthStar Retail — Azure Digital Twin (Build-Along Skeleton)

Welcome to the Reinvention Garage build-along. You are going to build a **Digital
Twin** of NorthStar Retail's Azure infrastructure: inject one of 5 fault scenarios
and watch a **7-agent Azure AI Foundry** incident-response flow drive it to
resolution — creating a real ServiceNow ticket, with two Human-in-the-Loop pauses.

You are **not** starting from an empty folder. This skeleton already ships the
frozen plumbing and the entire visual layout. You build the **logic** by pasting
the prompts from the **Build Guide** (`northstar-guide.html`) into your AI
assistant (Claude Code or GitHub Copilot), one phase at a time.

---

## How to use this skeleton

1. Open this folder in **VS Code** and start your AI assistant **inside it**.
2. Open **`northstar-guide.html`** in a browser — read the *Fundamentals*,
   *Agentic*, *Setup* and *ServiceNow* tabs, then work the **Build Guide** tab
   top to bottom.
3. `cp .env.example .env` and fill it in as you go (ServiceNow now; Foundry after
   Phase 4).
4. After each phase, run that phase's **checkpoint** before moving on.

> Each file you build starts as a **`SKELETON STUB`** — open it and you'll see a
> banner naming its phase and the contract it must satisfy. That is your target.

---

## What's already built vs. what you'll build

**✅ Pre-shipped (frozen — do not rewrite; the build depends on these being stable):**

| Area | Files |
|------|-------|
| Data model | `backend/schema.sql` (the 9 tables) |
| Live sampler | `backend/sampler.py` (moving time-series so graphs animate) |
| MCP server | `mcp-server/server.py` + `requirements.txt` (the 6 declared tools) |
| Agent contract | `af-agents/*.md` (7 runtime prompts + `README.md` = the I/O contract) |
| Frontend config | `package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `public/` |
| Frontend frozen | `src/main.tsx`, `src/index.css`, `src/types.ts`, `src/Canvas.tsx`, `src/metricMeta.ts`, `src/statusStyles.ts` |

**🛠️ You build (stubbed — the Build Guide phase prompts rebuild these):**

| Phase | Files |
|-------|-------|
| **1** Data foundation | `backend/db.py` (+ static seed) |
| **2** Fault injector | `backend/seed.py` (`--mode normal` / `--mode anomaly`) |
| **3** MCP client | `backend/mcp_client.py` |
| **4** AF agents | *(authored in the Foundry portal from `af-agents/*.md` — no file here)* |
| **5** Executor | `backend/executor.py` (the hub / agent loop) |
| **6** FastAPI | `backend/main.py` (REST + SSE) |
| **7** Frontend | `src/api.ts`, the 3 hooks (`useEventStream`, `useResourcesPoll`, `useActiveIncidentDetail`), and the panels/pages (`App`, `NavBar`, `HomePage`, `OrchestrationPage`, `SLD`, `LiveMetrics`, `TrendRecorder`, `FaultPanel`, `HitlPanel`, `ActivityLog`) |
| **8** Wire HITL + dry run | connect the two HITL pauses; run all 5 scenarios end-to-end |

The **layout is already perfect** — the frozen `Canvas.tsx`, `types.ts`, CSS and
config lock it in, and the Phase 7 prompts rebuild each panel to match.

---

## Running it (after you've built the relevant phases)

Backend (Python 3.12+):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/seed.py --mode normal
python -m uvicorn main:app --app-dir backend --port 8000   # --app-dir is required
```

Frontend (Node 20+):
```bash
cd frontend && npm install && npm run dev      # http://localhost:5173
```

Foundry auth is keyless Azure AD (no API key). If agent calls start failing:
```bash
az login --scope https://ai.azure.com/.default
```

There is **no automated test suite** — you verify by running `seed.py`, hitting
the REST/SSE endpoints, and exercising the app in the browser. `npm run build`
is your frontend typecheck gate.

---

## The one idea to keep in your head

**The AF agents are blind and stateless; the backend executor is the only hub.**
Each Foundry agent sees only its system prompt, the JSON payload you feed it this
turn, and a menu of allowed tool/agent names. It cannot touch the DB, call a
tool, or call another agent — it just emits **one JSON decision**. `executor.py`
performs every hop and every MCP tool call, writes the DB, and streams to the UI.
That's why MCP exists here and why the canvas is hub-and-spoke.

See `CLAUDE.md` for the invariants that will bite you if broken.
