# NorthStar Reliability Governor

## Proposal

Add a standalone SLO and error-budget reliability layer to the NorthStar Digital Twin. The layer continuously evaluates simulated service health and decides when reliability risk warrants investigation. When it detects a qualifying condition, it starts the existing incident-response workflow. The current agents still investigate, propose, and apply a fix; the new layer supplies the broader reliability context and evaluates the outcome.

The project remains a self-contained simulation. ServiceNow is not required: incidents, decisions, approvals, and post-incident summaries are stored and displayed locally.

## Why

The existing incident flow demonstrates how agents respond to a fault. A reliability governor extends the demonstration from a single incident to an ongoing operational objective: keeping a service within its reliability target over time.

A simple threshold watcher would only alert. This proposal makes the layer meaningfully agentic by having it assess the rate and impact of reliability degradation, choose an appropriate response mode, initiate the existing workflow when warranted, and verify whether the response protected the service objective.

## Goals

- Simulate a service-level objective (SLO), such as a monthly availability or request-success target.
- Track error-budget consumption and burn rate as simulated metrics change.
- Distinguish between normal operation, elevated risk, and a condition that should start incident response.
- Reuse the existing incident agents and human approval pauses for diagnosis and remediation.
- Evaluate service health and budget impact after remediation.
- Provide a local incident history and a clear explanation of each governor decision.
- Support repeatable scenarios that can be demonstrated without external ITSM credentials.

## Non-goals for the first version

- Connecting to a production observability platform or cloud environment.
- Automatically changing infrastructure without a simulation boundary or human approval.
- Replacing the incident-response agents or their existing responsibilities.
- Implementing a complete enterprise SLO management product with arbitrary SLI queries, calendars, and organization-wide policy management.
- Requiring ServiceNow. A future integration could be optional, but it is not part of the MVP.

## Responsibilities

### Reliability Governor: new outer loop

The governor evaluates service health across time. It owns the SLO policy, error-budget calculations, risk state, and decision to start or defer an incident run. It also evaluates whether the service recovered after a run.

### Incident workflow: existing inner loop

The existing workflow owns incident-level detection, analysis, root-cause analysis, fix recommendations, approved remediation, and incident reporting. The governor supplies the incident trigger and reliability context; it does not duplicate the incident agents' diagnosis or routing responsibilities.

## User-visible flow

1. A user selects an SLO policy and starts a simulation scenario.
2. The simulated service emits changing health metrics and traffic conditions.
3. The governor updates the current SLO status, remaining error budget, and burn rate.
4. If risk increases, the governor records why and either continues monitoring or starts the existing incident workflow according to policy.
5. Existing agents investigate the fault and propose a remediation. Human approval remains required for consequential actions, following the current HITL pattern.
6. The simulation applies the approved action and produces updated service metrics.
7. The governor observes a configurable recovery window, records whether the service recovered, and updates the incident outcome and budget impact.
8. The user can review the timeline, decisions, approvals, and final result locally.

## Governor decision states

- **HEALTHY**: SLO is on track and budget burn is within policy.
- **WATCH**: risk is elevated; continue collecting evidence and explain the signal.
- **INCIDENT_REQUIRED**: policy conditions are met; start one incident run for the affected service.
- **RECOVERY_CHECK**: remediation has been applied; assess the service during the recovery window.
- **RECOVERED**: health is back within policy for the required window.
- **UNRESOLVED**: health did not recover, or the budget risk remains above policy after the incident run.

The governor should avoid creating repeated incident runs for the same active service condition. It should retain a concise decision reason and the metric/policy evidence used for each state transition.

## Example scenario

A simulated deployment increases request failures while traffic is high. The governor notices that the error budget is burning faster than the selected policy allows. It moves from `HEALTHY` to `WATCH`, then to `INCIDENT_REQUIRED` once the configured trigger is sustained. The existing incident flow identifies the deployment as the likely cause and recommends a rollback. A human approves the rollback. After simulated metrics improve and remain healthy through the recovery window, the governor marks the service `RECOVERED` and records the impact on the error budget.

## Initial policy model

Keep the first policy deliberately small and understandable:

- SLO target and evaluation window.
- Metric used as the service-level indicator, such as request success rate.
- Warning and incident-trigger conditions, based on a sustained error rate or budget burn rate.
- Recovery window required before declaring recovery.
- Response mode: `monitor` or `start_incident`.

Threshold values should be configurable per scenario or policy, not embedded in agent prompts. The simulator should make the selected policy and its evidence visible to the user.

## MVP scope

1. Add a local SLO policy and error-budget calculation for one simulated service.
2. Add a governor evaluation loop that consumes the existing simulated metrics.
3. Add a decision history showing state changes, evidence, and reasons.
4. Start the existing incident workflow when the selected policy requires it, while preventing duplicate active runs.
5. After the incident completes, evaluate recovery and record the outcome.
6. Provide at least three repeatable scenarios: a brief transient spike that should only be watched, a sustained fault that should start an incident, and a successful remediation followed by recovery verification.
7. Keep incident records and summaries local; do not require a ServiceNow connection.

## Acceptance criteria

- A user can run the MVP end-to-end with no ServiceNow configuration.
- Error-budget and burn-rate values update from simulated service metrics and are explainable from the chosen policy.
- The transient-spike scenario does not start an incident when policy says to monitor.
- The sustained-fault scenario starts exactly one incident run for the active condition.
- The existing incident workflow, including its human approval pauses, remains responsible for diagnosis and remediation.
- The governor records the evidence and reason for each meaningful decision.
- After remediation, the recovery check can produce both `RECOVERED` and `UNRESOLVED` outcomes based on observed metrics.
- The user can inspect the service state, budget, incident timeline, approvals, and outcome in the app.

## Design considerations

- Treat this as a simulation: make simulated actions and resulting metric changes explicit in the UI.
- Keep policy evaluation deterministic for repeatable demonstrations; agents can explain or recommend, but core budget math and trigger checks should be ordinary backend logic.
- Keep the governor's state machine separate from the existing incident executor. Connect them through a narrow trigger and completion/result interface.
- Preserve the existing single-active-incident invariant unless the product explicitly expands to multiple services and concurrent incidents.
- Avoid counting the same simulated failure repeatedly or resetting the error budget unexpectedly; define the evaluation window and accounting rules before implementation.
- Continue to require human approval for remediation in the MVP. Any future autopilot mode should be an explicit simulation policy with visible guardrails.

## Open questions for the team

- Which SLO should the first demo use: availability, request success rate, or latency?
- Should the governor start incidents only from deterministic policy rules, or may an agent recommend a trigger that policy code then validates?
- Should the initial MVP support one service, or a small service group with dependencies?
- Should the error budget persist across simulation runs, or reset when a scenario starts?
- Where should the reliability view live in the current UI: a new page or an addition to the existing overview?

## Suggested implementation sequence

1. Agree on the first SLI/SLO and error-budget accounting rules.
2. Implement deterministic calculations and a few unit-level examples before connecting any agents.
3. Add the governor state machine and local decision history.
4. Connect `INCIDENT_REQUIRED` to the existing incident workflow and define how completion is reported back.
5. Build the three repeatable scenarios and validate the acceptance criteria.
6. Add the reliability view and a local post-incident summary.
