"""
NorthStar Retail Digital Twin -- live metrics sampler (Phase 6 extension).

Continuously appends jittered time-series rows to resource_metrics so the UI
can draw moving historical graphs. Faults are modeled as a "profile flip": a
resource is either "normal" (values sampled inside its healthy threshold band)
or "faulted" (the active scenario's injected values, lightly jittered, for the
metrics that scenario touches; its other metrics stay normal).

Ownership / boundaries:
  - This module NEVER sets is_anomaly (stays NULL, like seed.py) -- the Detect
    agent decides and the executor writes 0/1. The sampler only writes raw
    values, exactly like the seed script does.
  - All DB access goes through db.py (fresh connection per call), so the
    blocking writes are safe to run from a worker thread via asyncio.to_thread.
  - Static seeding is main.py's responsibility (it calls seed.seed_static_data
    on startup); the sampler assumes resources + thresholds already exist.

Profile state is a simple in-memory dict guarded by a lock:
    resource_id -> {"mode": "normal"|"faulted", "scenario_id": int|None}
Anything not present defaults to normal.

Env knobs:
    SAMPLER_INTERVAL_S   sampling cadence in seconds (default 2.0)
    HISTORY_WINDOW_MIN   prune rows older than this many minutes (default 15)
"""

from __future__ import annotations

import asyncio
import os
import random
import threading
from typing import Optional

import db

SAMPLER_INTERVAL_S = float(os.getenv("SAMPLER_INTERVAL_S", "2.0"))
HISTORY_WINDOW_MIN = int(os.getenv("HISTORY_WINDOW_MIN", "15"))

_NORMAL = {"mode": "normal", "scenario_id": None}

_profiles: dict[int, dict] = {}
_lock = threading.Lock()


# --------------------------------------------------------------------------
# Profile state
# --------------------------------------------------------------------------
def set_faulted(resource_id: int, scenario_id: int) -> None:
    with _lock:
        _profiles[resource_id] = {"mode": "faulted", "scenario_id": scenario_id}


def set_normal(resource_id: int) -> None:
    with _lock:
        _profiles[resource_id] = dict(_NORMAL)


def set_all_normal() -> None:
    with _lock:
        _profiles.clear()


def get_profile(resource_id: int) -> dict:
    with _lock:
        return dict(_profiles.get(resource_id, _NORMAL))


# --------------------------------------------------------------------------
# Value generation
# --------------------------------------------------------------------------
def _normal_value(threshold: dict) -> float:
    """A value comfortably inside [normal_min, normal_max] with small jitter,
    centered so it never brushes the warning line."""
    lo, hi = threshold.get("normal_min"), threshold.get("normal_max")
    if lo is None or hi is None:
        return 0.0
    span = hi - lo
    center = lo + span * 0.5
    jitter = span * 0.15
    value = center + random.uniform(-jitter, jitter)
    value = max(lo, min(hi, value))
    return round(value, 2)


def _faulted_value(injected_value: float) -> float:
    """The scenario's injected value with +/-~2% jitter; kept clearly
    anomalous and non-negative."""
    magnitude = abs(injected_value) * 0.02
    value = injected_value + random.uniform(-magnitude, magnitude)
    return round(max(0.0, value), 2)


# --------------------------------------------------------------------------
# Blocking writers (run inside asyncio.to_thread)
# --------------------------------------------------------------------------
def _write_samples_for_resource(resource_id: int) -> None:
    """Append ONE sample per metric this resource tracks. FAULTED scenario
    metrics use the injected value (jittered); everything else is normal."""
    profile = get_profile(resource_id)
    thresholds = db.get_thresholds(resource_id=resource_id)

    injected: dict[str, tuple[float, Optional[str]]] = {}
    if profile["mode"] == "faulted" and profile["scenario_id"] is not None:
        for row in db.get_scenario_metrics(profile["scenario_id"]):
            if row["resource_id"] == resource_id:
                injected[row["metric_name"]] = (row["injected_value"], row["unit"])

    for t in thresholds:
        metric = t["metric_name"]
        if metric in injected:
            raw, unit = injected[metric]
            value = _faulted_value(raw)
            unit = unit or t["unit"]
        else:
            value = _normal_value(t)
            unit = t["unit"]
        db.insert_resource_metric(
            resource_id=resource_id,
            metric_name=metric,
            value=value,
            unit=unit,
            is_anomaly=None,  # sampler never sets anomaly -- the executor does
        )


def _write_all_samples() -> None:
    for resource in db.get_resources():
        _write_samples_for_resource(resource["id"])


# --------------------------------------------------------------------------
# Public async surface
# --------------------------------------------------------------------------
async def sample_once(resource_id: int) -> None:
    """Write one sample set for a resource immediately (used by inject so the
    Detect agent sees the fault on its first read)."""
    await asyncio.to_thread(_write_samples_for_resource, resource_id)


async def run_sampler() -> None:
    """Background loop: every SAMPLER_INTERVAL_S append a sample set for every
    resource, then prune old rows. One bad tick never kills the loop; cancels
    cleanly."""
    while True:
        try:
            await asyncio.to_thread(_write_all_samples)
            await asyncio.to_thread(db.prune_resource_metrics, HISTORY_WINDOW_MIN)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # never let one tick kill the sampler
            print(f"[sampler] tick error: {e}")
        try:
            await asyncio.sleep(SAMPLER_INTERVAL_S)
        except asyncio.CancelledError:
            raise
