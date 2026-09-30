# Error Budget Watcher

## Proposal

Add an SLO and error-budget reliability layer to the NorthStar Digital Twin. The dashboard continuously refreshes a deterministic reliability snapshot from the live sampler. When a user injects a fault, the policy evaluates the affected resource and starts the existing incident-response workflow only at HIGH risk. Existing Foundry agents investigate and recommend remediation; human approval remains in place before fixes and ServiceNow ticket submission.

The project remains a self-contained simulation. ServiceNow is not required: incidents, decisions, approvals, and post-incident summaries are stored and displayed locally.

## Why

The existing incident flow demonstrates how agents respond to a fault. A reliability governor extends the demonstration from a single incident to an ongoing operational objective: keeping a service within its reliability target over time.

A simple threshold watcher would only alert. This design combines deterministic SLO math and risk gating with the existing agent orchestration, human approvals, and ServiceNow MCP integration. Policy math stays explainable and repeatable; the agents handle incident diagnosis and remediation proposals.

## Goals

- Use a 99.9% availability target and a 30-day, 43.2-minute error budget for the storefront.
- Derive availability, observed budget consumption, remaining budget, burn rate, and exhaustion forecast from sampled error rates.
- Show LOW, MEDIUM, and HIGH risk with metric evidence and deterministic recommendations.
- Gate the existing incident workflow on HIGH risk; preserve its Foundry agents and human approval pauses.
- Reuse the NorthStar fault scenarios, metrics table, digital-twin map, incident history, and orchestration canvas.
- Keep the dashboard and policy calculations runnable locally; external agent/ticket actions require credentials.

## Non-goals for the first version

- Connecting to production observability or changing real infrastructure.
- Automatically applying remediation or submitting ServiceNow tickets without human approval.
- Replacing the existing incident-response agents or their responsibilities.
- Configurable multi-service SLO policy, calendar-aware windows, or long-term metric retention.
- Claiming a full 30-day measured history: the simulator retains 15 minutes by default.

## Responsibilities

### Reliability policy: outer decision layer

The policy owns the SLO target, error-budget calculations, risk state, forecast, and decision to start or defer an incident run. The current implementation refreshes status from retained sampler history and evaluates the affected resource when a fault is injected.

### Incident workflow: existing inner loop

The existing workflow owns incident-level detection, analysis, root-cause analysis, fix recommendations, approved remediation, and incident reporting. The governor supplies the incident trigger and reliability context; it does not duplicate the incident agents' diagnosis or routing responsibilities.

## User-visible flow

1. The app starts the sampler and displays a 99.9% SLO for the customer storefront.
2. The user injects one of the existing NorthStar fault scenarios.
3. The policy evaluates the affected resource's latest metrics and retained error-rate samples.
4. LOW or MEDIUM risk remains in monitoring. HIGH risk starts one existing incident run.
5. Foundry agents investigate and propose remediation; the user approves the fix and ticket through the existing HITL controls.
6. The simulator applies the approved fix, and the dashboard reflects new service metrics.
7. The user can review current budget, policy evidence, incident activity, approvals, and the ticket result.

## Risk states

- **LOW**: burn rate and sampled resource metrics are within policy.
- **MEDIUM**: burn rate is at least 6x, or a monitored metric crosses its warning threshold; continue monitoring.
- **HIGH**: burn rate is at least 14.4x, remaining budget is at most 20%, or a monitored metric crosses its critical threshold; start incident response on fault injection.

The API rejects another injected scenario while an incident is active. Each snapshot includes a reason and the metric/policy evidence that drove its risk state.

## Example scenario

A simulated deployment raises storefront errors and latency. The policy reports HIGH risk and a projected exhaustion time, then starts the existing incident flow. The agents identify a likely cause and recommend a fix. A human approves remediation and ticket submission; the sampler returns to normal and the dashboard reports the improved reliability snapshot.

## Initial policy model

The first policy is deliberately fixed and explainable:

- Target: 99.9% availability over a 30-day month (43.2 minutes allowed error budget).
- SLI proxy: sampled `error_rate_pct`; availability is `100 - error_rate_pct`.
- Consumption: sum each retained error-rate sample weighted by the configured sampler interval.
- Burn rate: current error rate divided by the allowed error fraction (0.1%).
- HIGH triggers: burn rate at least 14.4x, at most 20% budget remaining, or critical latency/CPU/memory.
- MEDIUM triggers: burn rate at least 6x or warning latency/CPU/memory.
- Response: LOW and MEDIUM monitor; HIGH starts the existing incident workflow when a fault scenario is injected.

Thresholds and math live in backend code, not agent prompts. The dashboard shows
the retained evidence-window length so a short simulation is not confused with
30 days of production history.

## MVP scope

1. Show live reliability status for the customer storefront, based on the existing metrics sampler.
2. Show availability, remaining and consumed error budget, burn rate, exhaustion forecast, risk evidence, and recommended action.
3. Evaluate each injected scenario against the policy and start the existing workflow only at HIGH risk.
4. Reuse the five repeatable NorthStar faults, seven Foundry agents, incident canvas, HITL approvals, and ServiceNow MCP tool.
5. Keep dashboard and deterministic calculations local; Foundry and ServiceNow credentials are needed only for the external agent/ticket path.

## Acceptance criteria

- A seeded baseline produces LOW risk and an error rate consistent with the 99.9% SLO.
- The 99.9% target yields a 43.2-minute budget for a 30-day window.
- Error-budget consumption uses observed retained samples and is labeled with its evidence-window limit.
- A fault with HIGH risk starts exactly one incident workflow; an active incident prevents a second run.
- Risk evidence and recommendations are visible alongside live NorthStar metrics.
- The existing incident workflow and human approvals remain responsible for diagnosis, fixes, and ticket submission.
- The dashboard and policy endpoint work without Foundry or ServiceNow credentials; those credentials are required to complete the external workflow.

## Design considerations and next steps

- Treat this as a simulation: make injected faults and resulting metric changes explicit.
- Keep policy evaluation deterministic; use Foundry agents for diagnosis and fix proposals, not core SLO arithmetic.
- The current budget is an estimate from a 15-minute retained sample window. Persisted rolling-window aggregation is needed before using it as a long-lived service SLO.
- Preserve the single-active-incident invariant and human approval for remediation and ticket creation.
- Next: add a transient-spike scenario and a sustained-fault scenario, persist budget aggregates across sampler retention, and add recovery-window verification after remediation.
