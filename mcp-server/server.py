#!/usr/bin/env python3
"""
NorthStar Retail Digital Twin -- MCP Server (Phase 3).

Declares the 6 tools listed in others/txt/requirements.txt (lines ~128-138):
    get_resource_metrics, get_thresholds, run_rca, suggest_fix, apply_fix,
    create_servicenow_ticket

These tools are DECLARED here and are only ever CALLED by the Web App
Executor via backend/mcp_client.py -- never by the AF agents directly (an
agent only *requests* a tool by name in its JSON decision; the executor
performs the actual MCP call).

Implementation choice: the REAL MCP Python SDK (`mcp` package), using its
high-level `MCPServer` ergonomic server class (the current SDK's equivalent
of the historical "FastMCP" helper) over the **stdio** transport. Tools are
plain Python functions decorated with `@app.tool()`; the SDK derives the
JSON input schema from type hints/docstrings and serializes dict returns to
JSON text content automatically. See GATE B contract published by
mcp-engineer for the frozen input/output JSON shape of each tool.

Data access rule (GATE A): every tool below reads/writes the DB ONLY through
backend/db.py functions -- never raw SQL. schema.sql / db.py / seed.py are
untouched.

Design principle preserved from requirements.txt: tools supply DATA (or, for
apply_fix/create_servicenow_ticket, perform a simulated/real ACTION). Tools
never decide what counts as an "anomaly" -- that judgment call belongs to the
Detect Agent (get_thresholds only returns reference numbers).

Run standalone (for manual smoke testing):
    python3 mcp-server/server.py
(it will sit waiting on stdio for a client -- normally spawned as a
subprocess by backend/mcp_client.py, not run directly by a human).
"""

from __future__ import annotations

import os
import random
import sys

import httpx
from dotenv import load_dotenv

from mcp.server.mcpserver import MCPServer

# --------------------------------------------------------------------------
# Wiring to backend/db.py (GATE A) -- the ONLY way this server touches the DB.
# --------------------------------------------------------------------------
_MCP_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_MCP_SERVER_DIR, ".."))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import db  # noqa: E402  (backend/db.py -- frozen GATE A surface)

# Load .env from the project root (SN_* vars). Safe no-op if the
# file does not exist yet (the orchestrator/user creates it later).
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


app = MCPServer(name="northstar-mcp-server")


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

def _latest_metrics_deduped(resource_id: int | None = None) -> list[dict]:
    """db.get_latest_metrics() can return >1 row per (resource_id,
    metric_name) when rows share an identical recorded_at timestamp (e.g.
    an anomaly seed run appended within the same second as a prior seed).
    Dedupe here to the highest-id (most recently inserted) row per group,
    per the QA note in the frozen GATE A contract.
    """
    rows = db.get_latest_metrics(resource_id)
    best: dict[tuple[int, str], dict] = {}
    for row in rows:
        key = (row["resource_id"], row["metric_name"])
        if key not in best or row["id"] > best[key]["id"]:
            best[key] = row
    return list(best.values())


def _is_abnormal(metric_row: dict, threshold_row: dict | None) -> bool:
    """True if metric_row's value has crossed the WARNING line for its
    threshold. Used internally by run_rca/suggest_fix to decide which
    metrics to reason/propose about -- this is data preparation for those
    tools' own findings, NOT the Detect Agent's anomaly verdict (that verdict
    is still made by the Detect Agent from get_thresholds() +
    get_resource_metrics() and written by the executor via
    db.set_metric_anomaly()).
    """
    if threshold_row is None:
        return False
    comparison = threshold_row["comparison"]
    warning = threshold_row["warning_value"]
    if warning is None:
        return False
    value = metric_row["value"]
    if comparison == "gt":
        return value >= warning
    if comparison == "lt":
        return value <= warning
    return False


def _resolve_resource_id(incident_id: int | None, resource_id: int | None) -> tuple[int, dict | None]:
    """Shared arg-resolution for run_rca/suggest_fix/apply_fix: accept either
    an incident_id (look up its resource_id) or an explicit resource_id.
    Returns (resource_id, incident_or_None). Raises ValueError on bad input.
    """
    incident = None
    if incident_id is not None:
        incident = db.get_incident(incident_id)
        if incident is None:
            raise ValueError(f"No incident found with id={incident_id}.")
        if resource_id is None:
            resource_id = incident["resource_id"]
    if resource_id is None:
        raise ValueError("Provide incident_id and/or resource_id.")
    return resource_id, incident


# --------------------------------------------------------------------------
# Tool 1: get_resource_metrics
# --------------------------------------------------------------------------

@app.tool()
def get_resource_metrics(resource_id: int | None = None) -> dict:
    """Read CURRENT (latest) simulated metric values from the DB.

    Deduped to the newest row per (resource_id, metric_name). Optionally
    scoped to a single resource. Does NOT evaluate anomalies -- it only
    supplies data for the calling agent (via the executor) to reason over.
    """
    rows = _latest_metrics_deduped(resource_id)
    resource_cache: dict[int, tuple[dict | None, dict | None]] = {}
    metrics = []
    for row in rows:
        rid = row["resource_id"]
        if rid not in resource_cache:
            resource = db.get_resource(rid)
            rg = db.get_resource_group(resource["resource_group_id"]) if resource else None
            resource_cache[rid] = (resource, rg)
        resource, rg = resource_cache[rid]
        metrics.append(
            {
                "resource_id": rid,
                "resource_name": resource["name"] if resource else None,
                "display_name": resource["display_name"] if resource else None,
                "resource_type": resource["type"] if resource else None,
                "resource_group": rg["name"] if rg else None,
                "status": resource["status"] if resource else None,
                "metric_name": row["metric_name"],
                "value": row["value"],
                "unit": row["unit"],
                "recorded_at": row["recorded_at"],
            }
        )
    metrics.sort(key=lambda m: (m["resource_id"], m["metric_name"]))
    return {"metrics": metrics}


# --------------------------------------------------------------------------
# Tool 2: get_thresholds
# --------------------------------------------------------------------------

@app.tool()
def get_thresholds(resource_id: int | None = None, metric_name: str | None = None) -> dict:
    """Return threshold REFERENCE DATA only (normal_min/max, warning_value,
    critical_value, comparison). This tool does NOT flag anomalies -- the
    Detect Agent compares get_resource_metrics() values against this
    reference data and decides for itself what is anomalous.
    """
    rows = db.get_thresholds(resource_id=resource_id, metric_name=metric_name)
    resource_cache: dict[int, dict | None] = {}
    thresholds = []
    for row in rows:
        rid = row["resource_id"]
        if rid not in resource_cache:
            resource_cache[rid] = db.get_resource(rid)
        resource = resource_cache[rid]
        thresholds.append(
            {
                "resource_id": rid,
                "resource_name": resource["name"] if resource else None,
                "metric_name": row["metric_name"],
                "normal_min": row["normal_min"],
                "normal_max": row["normal_max"],
                "warning_value": row["warning_value"],
                "critical_value": row["critical_value"],
                "comparison": row["comparison"],
                "unit": row["unit"],
            }
        )
    return {"thresholds": thresholds}


# --------------------------------------------------------------------------
# Tool 3: run_rca
# --------------------------------------------------------------------------

@app.tool()
def run_rca(incident_id: int | None = None, resource_id: int | None = None) -> dict:
    """Identify root cause from metric patterns: compares the affected
    resource's current metrics vs its thresholds, ranks findings by
    severity, and checks sibling resources in the same resource group for
    cascade signals. Provide incident_id and/or resource_id (at least one).
    Returns a structured RCA finding for the calling agent to reason over
    and phrase in its own words -- this tool does not write incidents.rca_summary
    (the executor does that via db.update_incident_rca once the RCA Agent
    responds).
    """
    resource_id, incident = _resolve_resource_id(incident_id, resource_id)
    resource = db.get_resource(resource_id)
    if resource is None:
        raise ValueError(f"No resource found with id={resource_id}.")
    rg = db.get_resource_group(resource["resource_group_id"])
    scenario = db.get_scenario(incident["scenario_id"]) if incident else None

    thresholds = {t["metric_name"]: t for t in db.get_thresholds(resource_id=resource_id)}
    findings = []
    for metric in _latest_metrics_deduped(resource_id):
        threshold = thresholds.get(metric["metric_name"])
        severity = "normal"
        deviation_pct = None
        if threshold:
            comparison = threshold["comparison"]
            critical = threshold["critical_value"]
            warning = threshold["warning_value"]
            value = metric["value"]
            if comparison == "gt":
                if critical is not None and value >= critical:
                    severity = "critical"
                elif warning is not None and value >= warning:
                    severity = "warning"
                if critical:
                    deviation_pct = round((value - critical) / critical * 100, 1)
            elif comparison == "lt":
                if critical is not None and value <= critical:
                    severity = "critical"
                elif warning is not None and value <= warning:
                    severity = "warning"
                if critical:
                    deviation_pct = round((critical - value) / critical * 100, 1)
        findings.append(
            {
                "metric_name": metric["metric_name"],
                "value": metric["value"],
                "unit": metric["unit"],
                "recorded_at": metric["recorded_at"],
                "normal_min": threshold["normal_min"] if threshold else None,
                "normal_max": threshold["normal_max"] if threshold else None,
                "warning_value": threshold["warning_value"] if threshold else None,
                "critical_value": threshold["critical_value"] if threshold else None,
                "comparison": threshold["comparison"] if threshold else None,
                "severity": severity,
                "deviation_pct": deviation_pct,
            }
        )

    severity_rank = {"critical": 0, "warning": 1, "normal": 2}
    findings.sort(key=lambda f: severity_rank[f["severity"]])

    worst = [f for f in findings if f["severity"] == "critical"] or [
        f for f in findings if f["severity"] == "warning"
    ]
    label = resource["display_name"] or resource["name"]
    if worst:
        metric_list = ", ".join(f"{f['metric_name']}={f['value']}{f['unit'] or ''}" for f in worst)
        root_cause = f"{label} ({resource['name']}) is showing {worst[0]['severity']}-level metrics: {metric_list}."
    else:
        root_cause = f"No metric on {label} ({resource['name']}) is currently past its warning/critical threshold."

    cascade_notes = None
    if rg is not None:
        sibling_hits = []
        for sibling in db.get_resources(resource_group_id=resource["resource_group_id"]):
            if sibling["id"] == resource_id:
                continue
            sibling_thresholds = {t["metric_name"]: t for t in db.get_thresholds(resource_id=sibling["id"])}
            for metric in _latest_metrics_deduped(sibling["id"]):
                threshold = sibling_thresholds.get(metric["metric_name"])
                if _is_abnormal(metric, threshold):
                    sib_label = sibling["display_name"] or sibling["name"]
                    sibling_hits.append(f"{sib_label}.{metric['metric_name']}={metric['value']}{metric['unit'] or ''}")
        if sibling_hits:
            cascade_notes = (
                f"Other resources in {rg['name']} are also showing abnormal metrics "
                f"(possible cascade / shared root cause): " + "; ".join(sibling_hits)
            )

    return {
        "resource_id": resource_id,
        "resource_name": resource["name"],
        "display_name": resource["display_name"],
        "resource_group": rg["name"] if rg else None,
        "incident_id": incident_id,
        "scenario_name": scenario["name"] if scenario else None,
        "severity": scenario["severity"] if scenario else None,
        "findings": findings,
        "root_cause": root_cause,
        "cascade_notes": cascade_notes,
    }


# --------------------------------------------------------------------------
# Tool 4: suggest_fix
# --------------------------------------------------------------------------

# metric_name -> remediation option templates ({resource} filled with the
# resource's display name). Purely a lookup library; no DB writes here.
_FIX_LIBRARY: dict[str, list[str]] = {
    "response_time_ms": [
        "Scale out {resource} to additional instances/replicas to absorb load",
        "Enable/verify autoscale rules and front {resource} with a CDN or cache layer",
    ],
    "cpu_pct": [
        "Scale up {resource} to a higher compute tier (more vCPUs) or scale out horizontally",
        "Identify and throttle/kill the runaway process or query consuming CPU on {resource}",
    ],
    "memory_pct": [
        "Scale up {resource} to a higher-memory SKU",
        "Restart the {resource} service/process to clear a suspected memory leak",
    ],
    "error_rate_pct": [
        "Roll back the most recent deployment to {resource}",
        "Check {resource}'s dependent services (auth, DB, network) and add retry/circuit-breaker logic",
    ],
    "request_count": [
        "Restart the {resource} service/runtime -- request volume has dropped sharply",
        "Check the upstream trigger/queue feeding {resource} (event source, API route, schedule)",
    ],
    "connection_count": [
        "Increase {resource}'s max connection pool size / scale up its SKU",
        "Kill idle/leaked connections on {resource} and add client-side connection pooling",
    ],
}


@app.tool()
def suggest_fix(incident_id: int | None = None, resource_id: int | None = None) -> dict:
    """Propose remediation options (a list) appropriate to the affected
    resource's current abnormal metric(s). Provide incident_id and/or
    resource_id (at least one). Read-only: does NOT write incident_fixes --
    the executor persists the chosen list for the HITL #1 panel via
    db.insert_incident_fix() after the Suggest Agent responds.
    """
    resource_id, _incident = _resolve_resource_id(incident_id, resource_id)
    resource = db.get_resource(resource_id)
    if resource is None:
        raise ValueError(f"No resource found with id={resource_id}.")
    label = resource["display_name"] or resource["name"]

    thresholds = {t["metric_name"]: t for t in db.get_thresholds(resource_id=resource_id)}
    abnormal_metric_names = [
        m["metric_name"]
        for m in _latest_metrics_deduped(resource_id)
        if _is_abnormal(m, thresholds.get(m["metric_name"]))
    ]
    if not abnormal_metric_names:
        # Nothing crossed warning right now -- still give generic options
        # scoped to whatever metrics this resource tracks.
        abnormal_metric_names = list(thresholds.keys())[:1]

    fixes = []
    seen_descriptions: set[str] = set()
    for metric_name in abnormal_metric_names:
        for template in _FIX_LIBRARY.get(metric_name, []):
            description = template.format(resource=label)
            if description in seen_descriptions:
                continue
            seen_descriptions.add(description)
            fixes.append({"display_order": len(fixes) + 1, "description": description})

    fixes.append(
        {
            "display_order": len(fixes) + 1,
            "description": f"Escalate to the on-call engineer for {label} and monitor manually",
        }
    )

    return {"resource_id": resource_id, "resource_name": resource["name"], "fixes": fixes}


# --------------------------------------------------------------------------
# Tool 5: apply_fix
# --------------------------------------------------------------------------

@app.tool()
def apply_fix(
    resource_id: int,
    incident_id: int | None = None,
    fix_description: str | None = None,
) -> dict:
    """Simulate applying the fix: writes a fresh healthy resource_metrics
    row (sampled within each threshold's [normal_min, normal_max]) for
    every metric tracked on the resource, and sets the resource's status to
    Healthy. This is one of the two tools that actually MUTATE DB state
    (via db.py only -- insert_resource_metric / update_resource_status).
    """
    resource = db.get_resource(resource_id)
    if resource is None:
        raise ValueError(f"No resource found with id={resource_id}.")

    thresholds = db.get_thresholds(resource_id=resource_id)
    if not thresholds:
        raise ValueError(f"No thresholds configured for resource_id={resource_id}; cannot simulate a fix.")

    before = {m["metric_name"]: m for m in _latest_metrics_deduped(resource_id)}

    changed = []
    for threshold in thresholds:
        lo, hi = threshold["normal_min"], threshold["normal_max"]
        if lo is None or hi is None:
            continue
        new_value = round(random.uniform(lo, hi), 2)
        db.insert_resource_metric(
            resource_id=resource_id,
            metric_name=threshold["metric_name"],
            value=new_value,
            unit=threshold["unit"],
            is_anomaly=None,
        )
        old = before.get(threshold["metric_name"])
        changed.append(
            {
                "metric_name": threshold["metric_name"],
                "old_value": old["value"] if old else None,
                "new_value": new_value,
                "unit": threshold["unit"],
            }
        )

    db.update_resource_status(resource_id, "Healthy")
    label = resource["display_name"] or resource["name"]

    return {
        "success": True,
        "resource_id": resource_id,
        "resource_name": resource["name"],
        "incident_id": incident_id,
        "status": "Healthy",
        "metrics_fixed": changed,
        "fix_description": fix_description,
        "message": (
            f"Simulated fix applied to {label}: {len(changed)} metric(s) reset to healthy "
            f"range; resource status set to Healthy."
        ),
    }


# --------------------------------------------------------------------------
# Tool 6: create_servicenow_ticket
# --------------------------------------------------------------------------

class ServiceNowNotConfiguredError(RuntimeError):
    """Raised when SN_* env vars are missing/empty. Caught by the
    MCP framework and surfaced to the client as a clean is_error result
    (friendly message text, no raw stack trace) -- see mcp-engineer's GATE B
    report for the verified behavior.
    """


@app.tool()
def create_servicenow_ticket(
    short_description: str,
    description: str,
    urgency: str | None = None,
    category: str | None = None,
    incident_id: int | None = None,
) -> dict:
    """POST a new incident to the ServiceNow PDI Table API
    (POST {SN_INSTANCE}/api/now/table/incident) using HTTP Basic
    auth. Config comes ONLY from environment variables (loaded from the
    project-root .env via python-dotenv): SN_INSTANCE,
    SN_USER, SN_PASSWORD, and optionally
    SN_TICKET_TABLE (defaults to "incident"). If any required var is
    unset/empty, raises a clear, friendly ServiceNowNotConfiguredError
    (never a raw stack trace, never hard-codes a secret).
    """
    instance_url = (os.environ.get("SN_INSTANCE") or "").strip()
    user = (os.environ.get("SN_USER") or "").strip()
    password = (os.environ.get("SN_PASSWORD") or "").strip()
    table = (os.environ.get("SN_TICKET_TABLE") or "incident").strip() or "incident"

    if not instance_url or not user or not password:
        raise ServiceNowNotConfiguredError(
            "ServiceNow not configured: set SN_INSTANCE, SN_USER, "
            "and SN_PASSWORD in the project's .env file, then restart the app."
        )

    url = instance_url.rstrip("/") + f"/api/now/table/{table}"
    payload: dict[str, str] = {
        "short_description": short_description,
        "description": description,
    }
    if urgency:
        payload["urgency"] = urgency
    if category:
        payload["category"] = category

    try:
        response = httpx.post(
            url,
            json=payload,
            auth=(user, password),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=20.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"ServiceNow rejected the ticket request ({exc.response.status_code}): "
            f"{exc.response.text[:300]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Could not reach ServiceNow PDI at {instance_url}: {exc}") from exc

    result = response.json().get("result", {})
    ticket_number = result.get("number")
    sys_id = result.get("sys_id")
    if not ticket_number:
        raise RuntimeError(f"ServiceNow response did not include a ticket number: {response.text[:300]}")

    return {
        "ticket_number": ticket_number,
        "sys_id": sys_id,
        "url": (f"{instance_url.rstrip('/')}/nav_to.do?uri=incident.do?sys_id={sys_id}" if sys_id else None),
        "status": "created",
        "incident_id": incident_id,
    }


if __name__ == "__main__":
    app.run(transport="stdio")
