"""
================================ SKELETON STUB ================================
NorthStar Retail Digital Twin -- Web App Executor / Agent Loop  (executor.py)

  BUILD PHASE : 5 (the backend brain)
  BUILT BY    : the Phase 5 prompt in the Build Guide
  CONTRACT    : GATE C -- the agent I/O contract (per-agent payload + JSON
                decision schema + routing) is FROZEN in af-agents/README.md
                (already shipped). Build the loop against it.

THE ONE IDEA THAT EXPLAINS EVERYTHING
  The AF agents are BLIND and STATELESS. Each one only reads a JSON payload and
  emits ONE JSON decision (use_tool / handoff / none). It cannot touch the DB,
  call a tool, or call another agent. THIS module is the only hub: it performs
  every routing hop and every MCP tool call, feeds results back, writes the DB,
  and streams to the UI. That is why MCP exists here and why the canvas is
  hub-and-spoke.

WHAT YOU BUILD
  * call_af_agent(agent_name, payload)  -- prompt a Foundry agent by NAME via
    azure-ai-projects -> get_openai_client(agent_name=...) -> responses.create.
    The model passed MUST equal the agent's own model (auto-detect from project).
  * _build_payload / _ingest / _run_tool -- construct each agent's payload,
    parse its decision, run the requested MCP tool (via mcp_client), carry a
    context bag forward.
  * the drive loop: DETECTING -> ANALYZING -> DIAGNOSING -> AWAITING_FIX_APPROVAL
    -> FIXING -> AWAITING_TICKET_APPROVAL -> RESOLVED.
  * SSE emit() helper -- the frontend consumes these event types:
        activity, canvas, status, tool, hitl, resource_status, resolved, error
  * HITL: the loop PARKS on an asyncio.Future at AWAITING_FIX_APPROVAL and
    AWAITING_TICKET_APPROVAL until a REST POST resolves it
    (provide_fix_approval / provide_ticket_submission).

INVARIANTS (see CLAUDE.md)
  * is_anomaly is written ONLY here, from the Detect agent's `anomalies`.
  * Single active incident (incidents.is_active).
  * Canvas node IDs in _canvas_payload MUST match Canvas.tsx + types.ts
    (Executor, MCP, Orchestrator, Detect, Analyze, RCA, Suggest, Fix, Ticket)
    or the SSE-driven glow silently stops. Canvas.tsx is frozen -- match it.
==============================================================================
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from typing import Optional

import db
import mcp_client


TOOLS = {"get_resource_metrics", "get_thresholds", "run_rca", "suggest_fix", "apply_fix", "create_servicenow_ticket"}
AGENTS = {"Orchestrator", "Detect", "Analyze", "RCA", "Suggest", "Fix", "Ticket"}
_AGENT_ENV = {
  "Orchestrator": "ORCHESTRATOR_AGENT", "Detect": "DETECT_AGENT", "Analyze": "ANALYZE_AGENT",
  "RCA": "RCA_AGENT", "Suggest": "SUGGEST_AGENT", "Fix": "FIX_AGENT", "Ticket": "TICKET_AGENT",
}
MAX_STEPS = 40
TOKEN_SCOPE = "https://ai.azure.com/.default"
DEFAULT_MODEL = "gpt-5"

_subscribers = set()
_current_run = None
_current_task = None
_foundry_lock = threading.Lock()
_foundry_client = None
_foundry_credential = None
_openai_clients = {}


def subscribe():
  queue = asyncio.Queue()
  _subscribers.add(queue)
  return queue


def unsubscribe(queue):
  _subscribers.discard(queue)


async def emit(event_type, data):
  event = {"type": event_type, "data": data}
  for queue in tuple(_subscribers):
    try:
      queue.put_nowait(event)
    except asyncio.QueueFull:
      pass


def _parse_decision(reply):
  text = reply.strip()
  if text.startswith("```"):
    lines = text.splitlines()[1:]
    if lines and lines[-1].strip() == "```":
      lines.pop()
    text = "\n".join(lines).strip()
  if text.lower().startswith("json"):
    text = text[4:].lstrip()
  decision = json.loads(text)
  if not isinstance(decision, dict):
    raise RuntimeError("Agent response must be a JSON object.")
  kind = decision.get("decision")
  if kind not in {"use_tool", "handoff", "none"}:
    raise RuntimeError(f"Invalid agent decision: {kind!r}")
  if kind == "use_tool" and decision.get("tool") not in TOOLS:
    raise RuntimeError(f"Invalid tool in agent decision: {decision.get('tool')!r}")
  if kind == "handoff" and decision.get("agent") not in AGENTS:
    raise RuntimeError(f"Invalid agent in handoff decision: {decision.get('agent')!r}")
  return decision


def _foundry_clients(agent_name):
  global _foundry_client, _foundry_credential
  agent_env = _AGENT_ENV[agent_name]
  configured_name = os.getenv(agent_env)
  if not configured_name:
    raise RuntimeError(f"Missing {agent_name} agent configuration: {agent_env}.")
  endpoint = os.getenv("FOUNDRY_ENDPOINT")
  if not endpoint:
    raise RuntimeError("Missing FOUNDRY_ENDPOINT.")
  with _foundry_lock:
    if _foundry_client is None:
      from azure.ai.projects import AIProjectClient
      from azure.identity import DefaultAzureCredential
      _foundry_credential = DefaultAzureCredential()
      _foundry_client = AIProjectClient(endpoint=endpoint, credential=_foundry_credential)
    if agent_name not in _openai_clients:
      _openai_clients[agent_name] = _foundry_client.get_openai_client(agent_name=configured_name)
    return _openai_clients[agent_name]


def _call_af_agent_sync(agent_name, payload):
  client = _foundry_clients(agent_name)
  for attempt in range(2):
    try:
      response = client.responses.create(model=os.getenv("FOUNDRY_MODEL") or DEFAULT_MODEL, input=json.dumps(payload))
      return _parse_decision(response.output_text)
    except Exception as error:
      if attempt == 1 or "timed out" not in str(error).lower():
        raise
      time.sleep(1)


async def call_af_agent(agent_name, payload) -> dict:
  if agent_name not in AGENTS:
    raise RuntimeError(f"Unknown agent: {agent_name}")
  return await asyncio.to_thread(_call_af_agent_sync, agent_name, payload)


def _canvas_payload(incident_id, node, mode, status):
  if node in {"Executor", "MCP"}:
    edge = {"from": "Executor", "to": "MCP"}
  elif node in AGENTS:
    edge = {"from": node, "to": "Executor"}
  else:
    edge = None
  return {"incident_id": incident_id, "active_node": node, "active_edge": edge, "mode": mode, "status": status}


class IncidentRun:
  def __init__(self, incident_id, auto_approve=False):
    self.incident_id = incident_id
    self.auto_approve = auto_approve
    self.status = "DETECTING"
    self.handoff_from = None
    self.ticket_submitted = False
    self.anomaly_persisted = False
    self.context = {}
    self.fix_future = None
    self.ticket_future = None
    self.done = asyncio.Event()
    self.finished_status = None


def get_current_run():
  return _current_run


async def _activity(run, agent_name, message_type, message):
  db.insert_agent_activity(run.incident_id, agent_name, message_type, message)
  rows = db.get_agent_activity(run.incident_id)
  await emit("activity", rows[-1])


async def _set_run_status(run, status):
  run.status = status
  db.update_incident_status(run.incident_id, status)
  await emit("status", {"incident_id": run.incident_id, "status": status})


def _incident_context(run):
  incident = db.get_incident(run.incident_id) or {}
  scenario = db.get_scenario(incident.get("scenario_id")) if incident.get("scenario_id") else None
  resource = db.get_resource(incident.get("resource_id")) if incident.get("resource_id") else None
  group = db.get_resource_group(resource["resource_group_id"]) if resource else None
  affected = run.context.get("affected_resource")
  if affected is None and resource:
    affected = {"resource_id": resource["id"], "resource_name": resource["name"], "display_name": resource["display_name"], "resource_group": group["name"] if group else None}
  return incident, scenario, affected or {}


def _build_payload(run, agent, tool_result=None):
  payload = {"incident_id": run.incident_id, "status": run.status}
  c = run.context
  if agent == "Detect":
    payload.update(metrics=c.get("detect_metrics"), thresholds=c.get("detect_thresholds"))
  elif agent == "Orchestrator":
    payload.update(handoff_from=run.handoff_from, anomalies=c.get("anomalies"), context={k: c[k] for k in ("affected_resource", "rca", "selected_fix", "fix_result", "ticket_number") if k in c})
  elif agent == "Analyze":
    payload.update(handoff_from=run.handoff_from, anomalies=c.get("anomalies"))
  elif agent == "RCA":
    payload.update(affected_resource=c.get("affected_resource"), tool_result=c.get("rca_tool_result"))
  elif agent == "Suggest":
    payload.update(affected_resource=c.get("affected_resource"), rca=c.get("rca"), tool_result=c.get("suggest_tool_result"))
  elif agent == "Fix":
    payload.update(affected_resource=c.get("affected_resource"), selected_fix=c.get("selected_fix"), tool_result=c.get("fix_tool_result"))
  elif agent == "Ticket":
    incident, scenario, affected = _incident_context(run)
    payload.update(severity=scenario["severity"] if scenario else None, detected_at=incident.get("detected_at"), resolved_at=incident.get("resolved_at"), affected_resource=affected, anomalies=c.get("anomalies", []), rca=c.get("rca", {}), fix_result=c.get("fix_result", {}), submit_approved=run.ticket_submitted, ticket_final=c.get("ticket_final"), tool_result=c.get("ticket_tool_result"))
  return payload


def _derive_status(resource_id):
  thresholds = {t["metric_name"]: t for t in db.get_thresholds(resource_id=resource_id)}
  severity = 0
  for metric in db.get_latest_metrics(resource_id=resource_id):
    threshold = thresholds.get(metric["metric_name"])
    if not threshold:
      continue
    value = metric["value"]
    if threshold["comparison"] == "gt":
      if threshold["critical_value"] is not None and value >= threshold["critical_value"]: severity = max(severity, 2)
      elif threshold["warning_value"] is not None and value >= threshold["warning_value"]: severity = max(severity, 1)
    elif threshold["comparison"] == "lt":
      if threshold["critical_value"] is not None and value <= threshold["critical_value"]: severity = max(severity, 2)
      elif threshold["warning_value"] is not None and value <= threshold["warning_value"]: severity = max(severity, 1)
  return "Critical" if severity == 2 else "Degraded" if severity == 1 else "Healthy"


def _update_resource_status(resource_id):
  status = _derive_status(resource_id)
  db.update_resource_status(resource_id, status)
  return status


def _persist_anomalies(run, anomalies):
  incident = db.get_incident(run.incident_id)
  resource_ids = {a.get("resource_id") for a in anomalies if a.get("resource_id") is not None}
  if incident and incident.get("resource_id"):
    resource_ids.add(incident["resource_id"])
  anomaly_keys = {(a.get("resource_id"), a.get("metric_name")) for a in anomalies}
  for resource_id in resource_ids:
    latest = {}
    for row in db.get_resource_metrics(resource_id=resource_id):
      if row["metric_name"] not in latest or row["id"] > latest[row["metric_name"]]["id"]:
        latest[row["metric_name"]] = row
    for row in latest.values():
      db.set_metric_anomaly(row["id"], int((resource_id, row["metric_name"]) in anomaly_keys))
    _update_resource_status(resource_id)


def _ingest(run, agent, decision):
  c = run.context
  if agent == "Detect":
    c["anomalies"] = decision.get("anomalies", [])
    if not run.anomaly_persisted:
      _persist_anomalies(run, c["anomalies"])
      run.anomaly_persisted = True
  elif agent == "Analyze":
    c["affected_resource"] = decision.get("affected_resource")
  elif agent == "RCA":
    c["rca"] = decision.get("rca", {})
    c["rca_summary"] = decision.get("rca_summary") or c["rca"].get("root_cause")
    if c["rca_summary"]: db.update_incident_rca(run.incident_id, c["rca_summary"])
  elif agent == "Suggest":
    c["fix_options"] = decision.get("fix_options", [])
    if not db.get_incident_fixes(run.incident_id):
      for option in c["fix_options"]: db.insert_incident_fix(run.incident_id, option.get("description", ""), option.get("display_order"))
  elif agent == "Fix":
    c["fix_result"] = decision.get("fix_result", {})
  elif agent == "Ticket":
    if decision.get("ticket_draft") is not None:
      c["ticket_draft"] = decision["ticket_draft"]
      db.update_incident_ticket_draft(run.incident_id, decision["ticket_draft"])
    if decision.get("ticket_number"): c["ticket_number"] = decision["ticket_number"]
    if decision.get("ticket_text"): c["ticket_text"] = decision["ticket_text"]


async def _run_tool(run, agent, tool):
  await emit("tool", {"incident_id": run.incident_id, "agent": agent, "tool": tool, "phase": "call"})
  await emit("canvas", _canvas_payload(run.incident_id, "MCP", "glow", run.status))
  incident, scenario, affected = _incident_context(run)
  resource_id = affected.get("resource_id") or incident.get("resource_id")
  if tool == "get_resource_metrics":
    result = await mcp_client.get_resource_metrics(resource_id); run.context["detect_metrics"] = result.get("metrics", [])
  elif tool == "get_thresholds":
    result = await mcp_client.get_thresholds(resource_id); run.context["detect_thresholds"] = result.get("thresholds", [])
  elif tool == "run_rca":
    result = await mcp_client.run_rca(run.incident_id, resource_id); run.context["rca_tool_result"] = result
  elif tool == "suggest_fix":
    result = await mcp_client.suggest_fix(run.incident_id, resource_id); run.context["suggest_tool_result"] = result
  elif tool == "apply_fix":
    selected = run.context.get("selected_fix") or {}
    result = await mcp_client.apply_fix(resource_id, run.incident_id, selected.get("description")); run.context["fix_tool_result"] = result
    import sampler
    sampler.set_normal(resource_id)
    status = _update_resource_status(resource_id)
    await emit("resource_status", {"incident_id": run.incident_id, "resource_id": resource_id, "status": status})
  elif tool == "create_servicenow_ticket":
    text = run.context.get("ticket_text") or run.context.get("ticket_final") or run.context.get("ticket_draft") or ""
    label = affected.get("display_name") or affected.get("resource_name") or str(resource_id)
    result = await mcp_client.create_servicenow_ticket(f"NorthStar incident {run.incident_id} - {label}", text, incident_id=run.incident_id)
    run.context["ticket_tool_result"] = result
    if result.get("ticket_number"): run.context["ticket_number"] = result["ticket_number"]
  else:
    raise RuntimeError(f"Unsupported tool: {tool}")
  await emit("tool", {"incident_id": run.incident_id, "agent": agent, "tool": tool, "phase": "result", "result": result})
  return result


async def _await_fix_approval(run):
  if run.auto_approve:
    fixes = db.get_incident_fixes(run.incident_id)
    return fixes[0]["id"] if fixes else None
  run.fix_future = asyncio.get_running_loop().create_future()
  return await run.fix_future


async def _await_ticket_submission(run):
  if run.auto_approve: return run.context.get("ticket_draft")
  run.ticket_future = asyncio.get_running_loop().create_future()
  return await run.ticket_future


async def _handle_none(run, agent):
  if agent == "Suggest":
    await _set_run_status(run, "AWAITING_FIX_APPROVAL")
    await emit("canvas", _canvas_payload(run.incident_id, "Suggest", "slow_throb", run.status))
    fixes = db.get_incident_fixes(run.incident_id)
    await emit("hitl", {"incident_id": run.incident_id, "hitl": 1, "fix_options": [{"id": f["id"], "display_order": f["display_order"], "description": f["description"]} for f in fixes]})
    fix_id = await _await_fix_approval(run)
    if fix_id is None: raise RuntimeError("No fix option is available for approval.")
    db.select_incident_fix(fix_id)
    selected = next(f for f in db.get_incident_fixes(run.incident_id) if f["id"] == fix_id)
    run.context["selected_fix"] = selected
    await _activity(run, "Human", "HUMAN", f"Fix approved: {selected['description']}")
    run.handoff_from = "Suggest"
    return "RESUME_FIX"
  if agent == "Ticket" and not run.ticket_submitted:
    await _set_run_status(run, "AWAITING_TICKET_APPROVAL")
    await emit("canvas", _canvas_payload(run.incident_id, "Ticket", "slow_throb", run.status))
    await emit("hitl", {"incident_id": run.incident_id, "hitl": 2, "ticket_draft": run.context.get("ticket_draft")})
    final_text = await _await_ticket_submission(run)
    run.context["ticket_final"] = final_text
    db.update_incident_ticket_final(run.incident_id, final_text)
    run.ticket_submitted = True
    await _activity(run, "Human", "HUMAN", "ServiceNow ticket submitted for creation.")
    return "RESUME_TICKET"
  ticket_number = run.context.get("ticket_number")
  db.resolve_incident(run.incident_id, ticket_number)
  run.status = run.finished_status = "RESOLVED"
  await emit("status", {"incident_id": run.incident_id, "status": "RESOLVED"})
  await emit("canvas", _canvas_payload(run.incident_id, "Orchestrator", "idle", "RESOLVED"))
  await emit("resolved", {"incident_id": run.incident_id, "status": "RESOLVED", "servicenow_ticket_no": ticket_number})
  return "RESOLVED"


async def _drive(run):
  agent, tool_result, steps = "Detect", None, 0
  while steps < MAX_STEPS:
    steps += 1
    await emit("canvas", _canvas_payload(run.incident_id, agent, "glow", run.status))
    await _activity(run, agent, "INFO", f"Starting {agent} agent.")
    decision = await call_af_agent(agent, _build_payload(run, agent, tool_result))
    _ingest(run, agent, decision)
    await _activity(run, agent, "INFO", decision.get("reason", ""))
    tool_result = None
    if decision["decision"] == "use_tool":
      tool_result = await _run_tool(run, agent, decision["tool"])
    elif decision["decision"] == "handoff":
      run.handoff_from = agent
      next_agent = decision["agent"]
      if next_agent in {"Analyze", "RCA", "Fix"}:
        await _set_run_status(run, {"Analyze": "ANALYZING", "RCA": "DIAGNOSING", "Fix": "FIXING"}[next_agent])
      agent = next_agent
    else:
      token = await _handle_none(run, agent)
      if token == "RESOLVED": return
      agent = {"RESUME_FIX": "Orchestrator", "RESUME_TICKET": "Ticket"}[token]
  raise RuntimeError(f"Incident orchestration exceeded MAX_STEPS={MAX_STEPS}.")


async def run_incident(incident_id, auto_approve=False) -> IncidentRun:
  global _current_run
  run = IncidentRun(incident_id, auto_approve)
  _current_run = run
  try:
    await _drive(run)
  except Exception as error:
    run.finished_status = "ERROR"
    await _set_run_status(run, "ERROR")
    await _activity(run, "Executor", "ERROR", str(error))
    await emit("error", {"incident_id": incident_id, "message": str(error)})
  finally:
    if run.finished_status is None: run.finished_status = run.status
    run.done.set()
  return run


def launch_incident(incident_id, auto_approve=False) -> asyncio.Task:
  global _current_run, _current_task
  if _current_task is not None and not _current_task.done(): raise RuntimeError("An incident orchestration is already running.")
  _current_run = IncidentRun(incident_id, auto_approve)

  async def runner():
    run = _current_run
    try:
      await _drive(run)
    except Exception as error:
      run.finished_status = "ERROR"
      await _set_run_status(run, "ERROR")
      await _activity(run, "Executor", "ERROR", str(error))
      await emit("error", {"incident_id": incident_id, "message": str(error)})
    finally:
      if run.finished_status is None: run.finished_status = run.status
      run.done.set()
    return run

  _current_task = asyncio.create_task(runner())
  return _current_task


def provide_fix_approval(incident_id, fix_id):
  run = _current_run
  if run is None or run.incident_id != incident_id or run.fix_future is None or run.fix_future.done(): return False
  run.fix_future.set_result(fix_id)
  return True


def provide_ticket_submission(incident_id, ticket_final):
  run = _current_run
  if run is None or run.incident_id != incident_id or run.ticket_future is None or run.ticket_future.done(): return False
  run.ticket_future.set_result(ticket_final)
  return True


async def cancel_current_run(reason="baseline restored") -> Optional[int]:
  global _current_run, _current_task
  run, task = _current_run, _current_task
  if run is None or run.done.is_set(): return None
  if task is not None:
    task.cancel()
    try: await task
    except BaseException: pass
  await _activity(run, "Executor", "WARNING", f"Orchestration stopped — {reason}. Incident closed.")
  await emit("canvas", _canvas_payload(run.incident_id, "Orchestrator", "idle", run.status))
  await emit("resolved", {"incident_id": run.incident_id, "status": "RESOLVED", "servicenow_ticket_no": None})
  incident_id = run.incident_id
  _current_run = _current_task = None
  return incident_id
