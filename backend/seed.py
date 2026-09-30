#!/usr/bin/env python3
"""
================================ SKELETON STUB ================================
NorthStar Retail Digital Twin -- seed script  (seed.py)

  BUILD PHASE : 1 (static data) + 2 (the "fault injector")
  BUILT BY    : the Phase 1 and Phase 2 prompts in the Build Guide
  DEPENDS ON  : db.py (Phase 1) and schema.sql (frozen)

WHAT IT DOES (one script, two modes)
  python seed.py --mode normal
      Seed static data (resource_groups, resources, thresholds, scenarios,
      scenario_metrics) if not already present, then write a HEALTHY baseline
      into resource_metrics using each threshold's normal_min/normal_max.

  python seed.py --mode anomaly --scenario <1-5>
      Overwrite the affected resource's metrics with the anomalous values from
      scenario_metrics for that scenario.

PUBLIC SURFACE TO BUILD
  seed_static_data(), seed_normal(), seed_anomaly(scenario_id), main()

THE ONE RULE YOU MUST NOT BREAK
  seed.py NEVER sets is_anomaly. Writing raw values is all it does; the Detect
  agent decides what is an anomaly and the executor writes is_anomaly later.

NOTE ON THE LIVE APP
  At runtime the FaultPanel injects faults through the API (a sampler profile
  flip), NOT by re-running this script -- see sampler.py (frozen). This CLI
  path exists for the Phase 1/2 checkpoints and for seeding the baseline.
==============================================================================
"""

import argparse
import random
import sqlite3
import sys

import db


RESOURCE_GROUPS = [
  ("rg-prod-app", "Application Tier"),
  ("rg-prod-data", "Data Tier"),
]

RESOURCES = [
  ("rg-prod-app", "webapp-northstar", "WebApp", "Customer Storefront", "🌐"),
  ("rg-prod-app", "functionapp-orders", "FunctionApp", "Order Processing", "⚡"),
  ("rg-prod-app", "apim-gateway", "APIManagement", "API Gateway", "🚪"),
  ("rg-prod-data", "sql-orders-db", "SQLDatabase", "Orders Database", "🗄️"),
  ("rg-prod-data", "cosmos-catalog", "CosmosDB", "Product Catalog", "🌍"),
  ("rg-prod-data", "keyvault-secrets", "KeyVault", "Secrets & Certificates", "🔐"),
  ("rg-prod-data", "storage-blobs", "StorageAccount", "Blob Storage", "📦"),
  ("rg-prod-data", "vm-legacy-reporting", "VirtualMachine", "Legacy Reporting Server", "🖥️"),
]

THRESHOLDS = [
  ("response_time_ms", "ms", "gt", 50, 300, 1000, 3000),
  ("cpu_pct", "%", "gt", 10, 50, 70, 90),
  ("memory_pct", "%", "gt", 20, 60, 75, 90),
  ("error_rate_pct", "%", "gt", 0, 0.05, 1, 5),
  ("request_count", "count", "lt", 100, 1000, 50, 10),
  ("connection_count", "count", "gt", 5, 50, 80, 100),
]

SCENARIOS = [
  (1, "Black Friday Surge", "Web App response time spikes to 8500ms, error rate 40%", "webapp-northstar", "P1"),
  (2, "Database Meltdown", "SQL DB connections 100%, CPU 98%, query timeouts", "sql-orders-db", "P1"),
  (3, "Order Processing Fail", "Function App failure rate 85%, execution count drops to 0", "functionapp-orders", "P2"),
  (4, "Key Vault Lockout", "Key Vault access denied errors, secret retrieval failures", "keyvault-secrets", "P2"),
  (5, "VM CPU Overload", "VM (legacy reporting) CPU 99%, memory 97%, disk I/O maxed", "vm-legacy-reporting", "P3"),
]

SCENARIO_METRICS = {
  1: [("webapp-northstar", "response_time_ms", 8500, "ms"), ("webapp-northstar", "error_rate_pct", 40, "%")],
  2: [("sql-orders-db", "connection_count", 100, "count"), ("sql-orders-db", "cpu_pct", 98, "%"), ("sql-orders-db", "error_rate_pct", 45, "%")],
  3: [("functionapp-orders", "error_rate_pct", 85, "%"), ("functionapp-orders", "request_count", 0, "count")],
  4: [("keyvault-secrets", "error_rate_pct", 75, "%"), ("keyvault-secrets", "response_time_ms", 4000, "ms")],
  5: [("vm-legacy-reporting", "cpu_pct", 99, "%"), ("vm-legacy-reporting", "memory_pct", 97, "%")],
}


def _is_static_seeded() -> bool:
  try:
    return bool(db.get_resource_groups())
  except sqlite3.OperationalError:
    return False


def seed_static_data():
  group_ids = {}
  for name, description in RESOURCE_GROUPS:
    group_ids[name] = db.insert_resource_group(name, description)

  resource_ids = {}
  for group, name, type_, display_name, icon in RESOURCES:
    resource_ids[name] = db.insert_resource(group_ids[group], name, type_, display_name, icon)

  for resource_id in resource_ids.values():
    for metric_name, unit, comparison, normal_min, normal_max, warning_value, critical_value in THRESHOLDS:
      db.insert_threshold(resource_id, metric_name, normal_min, normal_max, warning_value, critical_value, comparison, unit)

  for scenario_id, name, description, affected_resource_name, severity in SCENARIOS:
    db.insert_scenario(scenario_id, name, description, resource_ids[affected_resource_name], severity)

  for scenario_id, metrics in SCENARIO_METRICS.items():
    for resource_name, metric_name, injected_value, unit in metrics:
      db.insert_scenario_metric(scenario_id, resource_ids[resource_name], metric_name, injected_value, unit)


def seed_normal():
  db.reset_db()
  seed_static_data()
  random.seed(42)
  for resource in db.get_resources():
    for threshold in db.get_thresholds(resource_id=resource["id"]):
      value = round(random.uniform(threshold["normal_min"], threshold["normal_max"]), 2)
      db.insert_resource_metric(resource["id"], threshold["metric_name"], value, threshold["unit"])
    db.update_resource_status(resource["id"], "Healthy")


def seed_anomaly(scenario_id):
  if not _is_static_seeded():
    db.init_db()
    seed_static_data()

  scenario = db.get_scenario(scenario_id)
  if scenario is None:
    print(f"Unknown scenario {scenario_id}. Valid range is 1-5.", file=sys.stderr)
    sys.exit(1)

  metrics = db.get_scenario_metrics(scenario_id)
  if not metrics:
    print(f"Scenario {scenario_id} has no scenario metrics. Valid range is 1-5.", file=sys.stderr)
    sys.exit(1)

  for metric in metrics:
    resource = db.get_resource(metric["resource_id"])
    db.insert_resource_metric(metric["resource_id"], metric["metric_name"], metric["injected_value"], metric["unit"])
    print(f"- {resource['name']}.{metric['metric_name']} = {metric['injected_value']} {metric['unit']}")


def main():
  parser = argparse.ArgumentParser(description="Seed NorthStar Digital Twin data")
  parser.add_argument("--mode", choices=("normal", "anomaly"), required=True)
  parser.add_argument("--scenario", type=int, choices=range(1, 6))
  args = parser.parse_args()
  if args.mode == "anomaly" and args.scenario is None:
    parser.error("--scenario is required when --mode anomaly")
  if args.mode == "normal":
    seed_normal()
  else:
    seed_anomaly(args.scenario)


if __name__ == "__main__":
  main()
