from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import asyncio
import json
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

import db
import executor
import mcp_client
import sampler
import seed


class InjectBody(BaseModel):
  scenario_id: int
  auto_approve: bool = False


class FixApprovalBody(BaseModel):
  incident_id: int
  fix_id: int


class TicketSubmitBody(BaseModel):
  incident_id: int
  ticket_final: str


app = FastAPI(title="NorthStar Retail Digital Twin", version="1.0")
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(
  CORSMiddleware,
  allow_origins=origins,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

_sampler_task = None


def _incident_detail(incident):
  if incident is None:
    return None
  return {
    "incident": incident,
    "scenario": db.get_scenario(incident["scenario_id"]),
    "resource": db.get_resource(incident["resource_id"]),
    "activity": db.get_agent_activity(incident["id"]),
    "fixes": db.get_incident_fixes(incident["id"]),
  }


@app.on_event("startup")
async def startup():
  global _sampler_task
  if not seed._is_static_seeded():
    await asyncio.to_thread(db.init_db)
    await asyncio.to_thread(seed.seed_static_data)
  _sampler_task = asyncio.create_task(sampler.run_sampler())


@app.on_event("shutdown")
async def shutdown():
  global _sampler_task
  if _sampler_task is not None:
    _sampler_task.cancel()
    try:
      await _sampler_task
    except asyncio.CancelledError:
      pass
    _sampler_task = None
  await mcp_client.close()


@app.get("/api/health")
async def health():
  return {"status": "ok"}


@app.get("/api/resources")
async def resources():
  latest = {}
  for row in db.get_latest_metrics():
    latest.setdefault(row["resource_id"], {})[row["metric_name"]] = row
  groups = []
  for group in db.get_resource_groups():
    group = dict(group)
    group["resources"] = []
    for resource in db.get_resources(group["id"]):
      resource = dict(resource)
      resource["metrics"] = list(latest.get(resource["id"], {}).values())
      group["resources"].append(resource)
    groups.append(group)
  return {"resource_groups": groups}


@app.get("/api/resources/{resource_id}/history")
async def resource_history(resource_id: int, minutes: int = Query(15, ge=1)):
  if db.get_resource(resource_id) is None:
    raise HTTPException(status_code=404, detail="Resource not found")
  thresholds = {}
  for threshold in db.get_thresholds(resource_id=resource_id):
    thresholds[threshold["metric_name"]] = {key: threshold[key] for key in (
      "normal_min", "normal_max", "warning_value", "critical_value", "comparison", "unit"
    )}
  return {
    "resource_id": resource_id,
    "window_minutes": minutes,
    "metrics": db.get_metric_history(resource_id, minutes),
    "thresholds": thresholds,
  }


@app.get("/api/scenarios")
async def scenarios():
  return {"scenarios": db.get_scenarios()}


@app.get("/api/incident/active")
async def active_incident():
  return {"incident": _incident_detail(db.get_active_incident())}


@app.get("/api/incident/{incident_id}")
async def incident(incident_id: int):
  detail = _incident_detail(db.get_incident(incident_id))
  if detail is None:
    raise HTTPException(status_code=404, detail="Incident not found")
  return detail


@app.get("/api/activity")
async def activity(incident_id: Optional[int] = None):
  return {"activity": db.get_agent_activity(incident_id)}


@app.post("/api/fault/inject")
async def inject_fault(body: InjectBody):
  if body.scenario_id < 1 or body.scenario_id > 5:
    raise HTTPException(status_code=400, detail="scenario_id must be between 1 and 5")
  scenario = db.get_scenario(body.scenario_id)
  if scenario is None:
    raise HTTPException(status_code=404, detail="Scenario not found")
  affected_id = scenario["affected_resource_id"]
  sampler.set_faulted(affected_id, body.scenario_id)
  await sampler.sample_once(affected_id)
  incident_id = db.create_incident(body.scenario_id, affected_id)
  try:
    executor.launch_incident(incident_id, auto_approve=body.auto_approve)
  except RuntimeError as error:
    db.deactivate_incident(incident_id)
    sampler.set_all_normal()
    raise HTTPException(status_code=409, detail=str(error))
  return {"incident_id": incident_id, "scenario_id": body.scenario_id, "status": "DETECTING"}


@app.post("/api/fault/restore")
async def restore_fault():
  await executor.cancel_current_run("operator clicked Restore Normal")
  sampler.set_all_normal()
  active = db.get_active_incident()
  if active is not None:
    db.deactivate_incident(active["id"])
  return {"status": "ok", "message": "Baseline restored to healthy."}


@app.post("/api/hitl/fix")
async def approve_fix(body: FixApprovalBody):
  if not executor.provide_fix_approval(body.incident_id, body.fix_id):
    raise HTTPException(status_code=409, detail="Incident is not waiting for fix approval")
  return {"status": "ok", "resumed": True}


@app.post("/api/hitl/ticket")
async def submit_ticket(body: TicketSubmitBody):
  if not executor.provide_ticket_submission(body.incident_id, body.ticket_final):
    raise HTTPException(status_code=409, detail="Incident is not waiting for ticket submission")
  return {"status": "ok", "resumed": True}


async def _events(request: Request):
  queue = executor.subscribe()
  try:
    yield {"event": "connected", "data": json.dumps({"active_incident": db.get_active_incident()}, default=str)}
    while not await request.is_disconnected():
      try:
        event = await asyncio.wait_for(queue.get(), timeout=15)
        yield {"event": event["type"], "data": json.dumps(event["data"], default=str)}
      except asyncio.TimeoutError:
        yield {"event": "heartbeat", "data": "{}"}
  finally:
    executor.unsubscribe(queue)


@app.get("/api/stream")
async def stream(request: Request):
  return EventSourceResponse(_events(request))


if __name__ == "__main__":
  import uvicorn
  uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), app_dir=str(Path(__file__).parent))
