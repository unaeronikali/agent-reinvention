# Azure AI Foundry Agents — Error Budget Watcher

Seven **runtime Azure AI Foundry agent system prompts**, authored in the Foundry portal. These are
not repository subagents and are not executed from these Markdown files; each file is the prompt
source to paste into its corresponding Foundry agent.

Every agent is **blind and stateless**: per turn it knows only (1) its system prompt, (2) the JSON
payload the executor feeds it, (3) a menu of allowed tool + agent names. It cannot touch the DB, run
a tool, or call another agent — it only READS the payload and EMITS one JSON decision. The **Web App
Executor (MCP Client)** is the hub for every agent<->agent and agent<->tool hop.

Files: `Orchestrator.md`, `Detect.md`, `Analyze.md`, `RCA.md`, `Suggest.md`, `Fix.md`, `Ticket.md`.

## Agent responsibilities

The reliability watcher is an outer, deterministic policy layer. Foundry agents run only inside
the incident-response workflow after policy code decides to open an incident.

| Watcher / workflow responsibility | Owner | Foundry agent? |
|------------------------------------|-------|----------------|
| Read live SLI and infrastructure metrics; identify threshold breaches | MCP metrics tools + `Detect` | Yes, `Detect` judges anomalies |
| Calculate 99.9% SLO, 43.2-minute monthly budget, burn rate, risk, and exhaustion estimate | Backend reliability policy | No; keep arithmetic deterministic |
| Show baseline risk guidance; explain the numeric forecast | Backend reliability policy | No separate model call in the current runtime |
| Coordinate the incident after a HIGH-risk policy decision | `Orchestrator` | Yes |
| Select the primary affected resource and signal | `Analyze` | Yes |
| Explain likely cause from telemetry | `RCA` + `run_rca` tool | Yes |
| Propose incident-specific remediation options | `Suggest` + `suggest_fix` tool | Yes; pauses for HITL #1 |
| Apply the human-approved simulated action | `Fix` + `apply_fix` tool | Yes; not a production change |
| Draft and submit a ServiceNow ticket | `Ticket` + MCP ticket tool | Yes; pauses for HITL #2 |

`Suggest` is the incident remediation agent, not the dashboard's policy calculator. The dashboard's
initial recommendations are deterministic rules. Do not add a standalone Error Budget Agent: it
would duplicate ordinary backend math. Do not add a Forecast or Recommendation prompt until the
executor has a real invocation path, payload contract, and tests for it. If natural-language
forecast explanations are later needed, add one bounded `ReliabilityAdvisor` rather than duplicating
the incident agents.

### Operating boundaries

- The backend owns SLO arithmetic, budget accounting, thresholds, risk state, and whether a fault
  starts incident response. Agents must not override those decisions.
- Agents are advisory and evidence-bound. Do not invent metrics, causes, remediation results, SLO
  values, or ticket outcomes absent from the current payload/tool result.
- `Fix` acts only through the simulator tool after a human selection. `Ticket` requests ServiceNow
  creation only after the human submits the draft.
- Preserve the exact agent/tool names and JSON output contracts below. A prompt-only new agent is
  not runnable: registration, payload construction, routing, environment configuration, and tests
  must be added to the executor first.

---

## FROZEN CONTRACT (GATE C — build the executor against this)

### Decision schema (every agent emits ONLY this JSON — no prose, no markdown fences)
```json
{
  "decision": "use_tool" | "handoff" | "none",
  "tool":  "<tool_name>",   // present ONLY when decision == "use_tool"
  "agent": "<AgentName>",   // present ONLY when decision == "handoff"
  "reason": "<short Activity Log status line>",   // ALWAYS present
  "...": "agent-specific fields (see per-agent below)"
}
```

### Frozen menus
- **Tools (GATE B):** `get_resource_metrics`, `get_thresholds`, `run_rca`, `suggest_fix`,
  `apply_fix`, `create_servicenow_ticket`.
- **Agents:** `Orchestrator`, `Detect`, `Analyze`, `RCA`, `Suggest`, `Fix`, `Ticket`.
- No agent may name a tool or agent outside these menus.

### Agent -> incident-status mapping
| Agent        | Drives status              | HITL          |
|--------------|----------------------------|---------------|
| Detect       | `DETECTING`                | —             |
| Analyze      | `ANALYZING`                | —             |
| RCA          | `DIAGNOSING`               | —             |
| Suggest      | `AWAITING_FIX_APPROVAL`    | **HITL #1**   |
| Fix          | `FIXING`                   | —             |
| Ticket       | `AWAITING_TICKET_APPROVAL` | **HITL #2**   |
| Orchestrator | routes across all; closes to `RESOLVED` | — |

### Routing model (hub-and-spoke via Orchestrator; every hop through the executor)
```
new incident (DETECTING)
  -> Detect  (get_resource_metrics -> get_thresholds -> reason)  --handoff--> Orchestrator
  -> Orchestrator (anomalies>0)                                  --handoff--> Analyze  (ANALYZING)
  -> Analyze                                                     --handoff--> Orchestrator
  -> Orchestrator                                               --handoff--> RCA      (DIAGNOSING)
  -> RCA (run_rca)                                               --handoff--> Orchestrator
  -> Orchestrator                                               --handoff--> Suggest
  -> Suggest (suggest_fix -> options)   decision:none => executor PAUSES  ⏸ HITL #1 (AWAITING_FIX_APPROVAL)
  -> [human picks option] -> executor -> Orchestrator (handoff_from=Suggest) --handoff--> Fix (FIXING)
  -> Fix (apply_fix)                                             --handoff--> Orchestrator
  -> Orchestrator                                               --handoff--> Ticket
  -> Ticket (draft)                     decision:none => executor PAUSES  ⏸ HITL #2 (AWAITING_TICKET_APPROVAL)
  -> [human edits+submits] -> executor -> Ticket turn2 (create_servicenow_ticket)
  -> executor -> Ticket turn3 (tool_result)                     --handoff--> Orchestrator
  -> Orchestrator (ticket_number set)   decision:none  => RESOLVED
```
Notes for the executor:
- **HITL pauses are executor-enforced.** An agent signals "step done, hold here" with
  `decision":"none"` plus its artifact (`fix_options` for Suggest, `ticket_draft` for Ticket).
  Agents never pause themselves and never route into a pause.
- **is_anomaly** is written by the executor from `Detect.anomalies`.
- The executor carries a `context` bag forward (affected_resource, rca, selected_fix, fix_result,
  ticket_number) and injects the fields each agent's payload declares.

### Per-agent input payload (what the executor feeds)  +  agent-specific output fields
| Agent | Key input fields | Agent-specific output fields |
|-------|------------------|------------------------------|
| Detect | `incident_id, status, metrics|null, thresholds|null` | `anomalies[]` (resource_id, resource_name, metric_name, value, unit, comparison, threshold_breached, threshold_value, reason) |
| Orchestrator | `incident_id, status, handoff_from, anomalies|null, context{}` | (none — routes only) |
| Analyze | `incident_id, status, handoff_from, anomalies[]` | `affected_resource{}` (resource_id, resource_name, display_name, metric_name, severity, value, unit) |
| RCA | `incident_id, status, affected_resource{}, tool_result(run_rca)|null` | `rca_summary` (string), `rca{}` (root_cause, cascade_notes, scenario_name, severity, findings[]) |
| Suggest | `incident_id, status, affected_resource{}, rca{}, tool_result(suggest_fix)|null` | `fix_options[]` (display_order, description) |
| Fix | `incident_id, status, affected_resource{}, selected_fix{}, tool_result(apply_fix)|null` | `fix_result{}` (status, fix_description, metrics_fixed[]) |
| Ticket | `incident_id, status, severity, detected_at, resolved_at, affected_resource{}, anomalies[], rca{}, fix_result{}, submit_approved(bool), ticket_final|null, tool_result(create_servicenow_ticket)|null` | `ticket_draft` (string, turn1), `ticket_text` (string, turn2), `ticket_number` (string, turn3) |

---

## CHECKPOINT — worked examples (sample payload in -> valid decision out)

**Detect** (both metrics + thresholds present) — payload:
`{"incident_id":42,"status":"DETECTING","metrics":[{"resource_id":5,"resource_name":"sql-northstar","metric_name":"cpu_pct","value":98.0,"unit":"%","recorded_at":"..."}],"thresholds":[{"resource_id":5,"metric_name":"cpu_pct","normal_min":10,"normal_max":70,"warning_value":85,"critical_value":95,"comparison":"gt","unit":"%"}]}`
=> `{"decision":"handoff","agent":"Orchestrator","reason":"Detected 1 critical anomaly on sql-northstar.","anomalies":[{"resource_id":5,"resource_name":"sql-northstar","metric_name":"cpu_pct","value":98.0,"unit":"%","comparison":"gt","threshold_breached":"critical","threshold_value":95.0,"reason":"98.0 >= critical 95.0 (gt)"}]}`

**Orchestrator** — payload:
`{"incident_id":42,"status":"ANALYZING","handoff_from":"Detect","anomalies":[{"resource_id":5,"metric_name":"cpu_pct","threshold_breached":"critical"}],"context":{}}`
=> `{"decision":"handoff","agent":"Analyze","reason":"Anomaly confirmed on sql-northstar — starting analysis."}`

**Analyze** — payload:
`{"incident_id":42,"status":"ANALYZING","handoff_from":"Orchestrator","anomalies":[{"resource_id":5,"resource_name":"sql-northstar","metric_name":"cpu_pct","value":98.0,"unit":"%","comparison":"gt","threshold_breached":"critical","threshold_value":95.0}]}`
=> `{"decision":"handoff","agent":"Orchestrator","reason":"Primary alert: cpu_pct on sql-northstar — critical.","affected_resource":{"resource_id":5,"resource_name":"sql-northstar","display_name":"sql-northstar","metric_name":"cpu_pct","severity":"critical","value":98.0,"unit":"%"}}`

**RCA** (turn 1) — payload:
`{"incident_id":42,"status":"DIAGNOSING","handoff_from":"Orchestrator","affected_resource":{"resource_id":5,"resource_name":"sql-northstar","metric_name":"cpu_pct"},"tool_result":null}`
=> `{"decision":"use_tool","tool":"run_rca","reason":"Running root cause analysis for sql-northstar."}`

**Suggest** (turn 2, fixes present) — payload:
`{"incident_id":42,"status":"DIAGNOSING","affected_resource":{"resource_id":5,"resource_name":"sql-northstar"},"tool_result":{"resource_id":5,"resource_name":"sql-northstar","fixes":[{"display_order":1,"description":"Scale up SQL DB and raise pool size."}]}}`
=> `{"decision":"none","reason":"Proposed 1 remediation option — awaiting human approval (HITL #1).","fix_options":[{"display_order":1,"description":"Scale up SQL DB and raise pool size."}]}`

**Fix** (turn 1) — payload:
`{"incident_id":42,"status":"FIXING","handoff_from":"Orchestrator","affected_resource":{"resource_id":5,"resource_name":"sql-northstar"},"selected_fix":{"display_order":1,"description":"Scale up SQL DB and raise pool size."},"tool_result":null}`
=> `{"decision":"use_tool","tool":"apply_fix","reason":"Applying approved fix to sql-northstar."}`

**Ticket** (turn 1, draft) — payload:
`{"incident_id":42,"status":"FIXING","handoff_from":"Orchestrator","severity":"P1","detected_at":"2026-08-23T10:01:00Z","resolved_at":"2026-08-23T10:07:30Z","affected_resource":{"resource_id":5,"resource_name":"sql-northstar","display_name":"Orders Database","resource_group":"rg-prod-data"},"anomalies":[{"metric_name":"cpu_pct","value":98.0,"unit":"%","threshold_breached":"critical"}],"rca":{"root_cause":"Connection pool exhaustion.","cascade_notes":"Retries amplified load.","scenario_name":"Database Meltdown"},"fix_result":{"fix_description":"Scaled SQL DB.","metrics_fixed":[{"metric_name":"cpu_pct","old_value":98.0,"new_value":22.0,"unit":"%"}]},"submit_approved":false,"ticket_final":null,"tool_result":null}`
=> `{"decision":"none","reason":"Ticket draft prepared for incident 42 — awaiting human review/submit (HITL #2).","ticket_draft":"Incident 42 | P1 | Database Meltdown\nAffected: sql-northstar (Orders Database), rg-prod-data\nDetected: 2026-08-23T10:01:00Z | Resolved: 2026-08-23T10:07:30Z\nAnomaly: cpu_pct 98% (critical breach)\nRoot cause: Connection pool exhaustion.\nCascade: Retries amplified load.\nFix applied: Scaled SQL DB (cpu_pct 98%->22%).\nSeverity: P1"}`

All seven produce parseable JSON using only frozen tool/agent names. Checkpoint satisfied.
