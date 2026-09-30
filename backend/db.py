"""
================================ SKELETON STUB ================================
NorthStar Retail Digital Twin -- SQLite access layer  (db.py)

  BUILD PHASE : 1  (Data Foundation)
  BUILT BY    : the Phase 1 prompt in the Build Guide (northstar-guide.html)
  CONTRACT    : GATE A -- this module is the ONLY surface that touches the DB.
                Nothing else in the app may run raw SQL. schema.sql (frozen,
                already shipped next to this file) is the 9-table data model.

WHY THIS IS A STUB
  You build db.py by prompting your AI assistant. It is the foundation every
  later phase imports (seed.py, mcp_client.py, executor.py, main.py all call
  these functions), so it comes first.

PUBLIC SURFACE TO BUILD (the frozen db.py API -- names other layers rely on)
  connection/lifecycle : get_connection, init_db, reset_db
  resource_groups      : insert_resource_group, get_resource_groups,
                         get_resource_group, get_resource_group_by_name
  resources            : insert_resource, get_resources, get_resource,
                         get_resource_by_name, update_resource_status
  resource_metrics     : insert_resource_metric, get_resource_metrics,
                         get_latest_metrics, set_metric_anomaly,
                         clear_resource_metrics, get_metric_history,
                         prune_resource_metrics
  thresholds           : insert_threshold, get_thresholds, get_threshold
  scenarios            : insert_scenario, get_scenarios, get_scenario
  scenario_metrics     : insert_scenario_metric, get_scenario_metrics
  incidents            : create_incident, get_active_incident, get_incident,
                         get_incidents, update_incident_status,
                         update_incident_rca, update_incident_ticket_draft,
                         update_incident_ticket_final, resolve_incident,
                         deactivate_incident
  incident_fixes       : insert_incident_fix, get_incident_fixes,
                         select_incident_fix
  agent_activity       : insert_agent_activity, get_agent_activity

KEY INVARIANTS (do not violate -- see CLAUDE.md)
  * seed.py writes RAW metric values only; is_anomaly stays NULL.
    is_anomaly is written ONLY by the executor (set_metric_anomaly).
  * Single active incident enforced at app level via incidents.is_active.
  * Priority is DERIVED from scenarios.severity -- there is no priority column.

TIP: prompt with schema.sql pasted in, and ask for helpers returning plain
     dicts (sqlite3.Row -> dict) so JSON serialization stays trivial.
==============================================================================
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "northstar.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def _now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _cutoff(older_than_minutes):
  return (datetime.fromisoformat(_now()) - timedelta(minutes=older_than_minutes)).isoformat()


def get_connection():
  connection = sqlite3.connect(DB_PATH)
  connection.row_factory = sqlite3.Row
  connection.execute("PRAGMA foreign_keys = ON")
  return connection


def _row_to_dict(row):
  return dict(row) if row is not None else None


def _rows_to_dicts(rows):
  return [dict(row) for row in rows]


def init_db(schema_path=SCHEMA_PATH):
  connection = get_connection()
  try:
    with open(schema_path, "r", encoding="utf-8") as schema_file:
      connection.executescript(schema_file.read())
    connection.commit()
  finally:
    connection.close()


def reset_db():
  if DB_PATH.exists():
    DB_PATH.unlink()
  init_db()


def insert_resource_group(name, description=None):
  connection = get_connection()
  try:
    cursor = connection.execute("INSERT INTO resource_groups (name, description) VALUES (?, ?)", (name, description))
    connection.commit()
    return cursor.lastrowid
  finally:
    connection.close()


def get_resource_groups():
  connection = get_connection()
  try:
    return _rows_to_dicts(connection.execute("SELECT * FROM resource_groups ORDER BY id"))
  finally:
    connection.close()


def get_resource_group(id):
  connection = get_connection()
  try:
    return _row_to_dict(connection.execute("SELECT * FROM resource_groups WHERE id = ?", (id,)).fetchone())
  finally:
    connection.close()


def get_resource_group_by_name(name):
  connection = get_connection()
  try:
    return _row_to_dict(connection.execute("SELECT * FROM resource_groups WHERE name = ?", (name,)).fetchone())
  finally:
    connection.close()


def insert_resource(resource_group_id, name, type_, display_name=None, icon=None, status="Healthy"):
  connection = get_connection()
  try:
    cursor = connection.execute("INSERT INTO resources (resource_group_id, name, type, display_name, icon, status, status_updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (resource_group_id, name, type_, display_name, icon, status, _now()))
    connection.commit()
    return cursor.lastrowid
  finally:
    connection.close()


def get_resources(resource_group_id=None):
  connection = get_connection()
  try:
    if resource_group_id is None:
      rows = connection.execute("SELECT * FROM resources ORDER BY id")
    else:
      rows = connection.execute("SELECT * FROM resources WHERE resource_group_id = ? ORDER BY id", (resource_group_id,))
    return _rows_to_dicts(rows)
  finally:
    connection.close()


def get_resource(id):
  connection = get_connection()
  try:
    return _row_to_dict(connection.execute("SELECT * FROM resources WHERE id = ?", (id,)).fetchone())
  finally:
    connection.close()


def get_resource_by_name(name):
  connection = get_connection()
  try:
    return _row_to_dict(connection.execute("SELECT * FROM resources WHERE name = ?", (name,)).fetchone())
  finally:
    connection.close()


def update_resource_status(resource_id, status):
  connection = get_connection()
  try:
    connection.execute("UPDATE resources SET status = ?, status_updated_at = ? WHERE id = ?", (status, _now(), resource_id))
    connection.commit()
  finally:
    connection.close()


def insert_resource_metric(resource_id, metric_name, value, unit=None, recorded_at=None, is_anomaly=None):
  connection = get_connection()
  try:
    timestamp = _now() if recorded_at is None else recorded_at
    cursor = connection.execute("INSERT INTO resource_metrics (resource_id, metric_name, value, unit, recorded_at) VALUES (?, ?, ?, ?, ?)", (resource_id, metric_name, value, unit, timestamp))
    connection.commit()
    return cursor.lastrowid
  finally:
    connection.close()


def get_resource_metrics(resource_id=None, metric_name=None):
  connection = get_connection()
  try:
    clauses, parameters = [], []
    if resource_id is not None:
      clauses.append("resource_id = ?")
      parameters.append(resource_id)
    if metric_name is not None:
      clauses.append("metric_name = ?")
      parameters.append(metric_name)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return _rows_to_dicts(connection.execute(f"SELECT * FROM resource_metrics{where} ORDER BY recorded_at, id", parameters))
  finally:
    connection.close()


def get_latest_metrics(resource_id=None):
  connection = get_connection()
  try:
    resource_filter = " AND m.resource_id = ?" if resource_id is not None else ""
    parameters = (resource_id,) if resource_id is not None else ()
    rows = connection.execute(f"""SELECT m.* FROM resource_metrics m
      JOIN (SELECT resource_id, metric_name, MAX(recorded_at) AS latest_at
          FROM resource_metrics GROUP BY resource_id, metric_name) latest
        ON latest.resource_id = m.resource_id AND latest.metric_name = m.metric_name
       AND latest.latest_at = m.recorded_at
      WHERE 1 = 1{resource_filter} ORDER BY m.resource_id, m.metric_name, m.id""", parameters)
    return _rows_to_dicts(rows)
  finally:
    connection.close()


def set_metric_anomaly(metric_id, is_anomaly):
  connection = get_connection()
  try:
    connection.execute("UPDATE resource_metrics SET is_anomaly = ? WHERE id = ?", (is_anomaly, metric_id))
    connection.commit()
  finally:
    connection.close()


def clear_resource_metrics(resource_id=None):
  connection = get_connection()
  try:
    if resource_id is None:
      cursor = connection.execute("DELETE FROM resource_metrics")
    else:
      cursor = connection.execute("DELETE FROM resource_metrics WHERE resource_id = ?", (resource_id,))
    connection.commit()
    return cursor.rowcount
  finally:
    connection.close()


def get_metric_history(resource_id, minutes=15):
  cutoff = _cutoff(minutes)
  connection = get_connection()
  try:
    rows = connection.execute("SELECT metric_name, recorded_at, value, unit FROM resource_metrics WHERE resource_id = ? AND recorded_at > ? ORDER BY metric_name, recorded_at, id", (resource_id, cutoff))
    history = {}
    for row in rows:
      history.setdefault(row["metric_name"], []).append({"recorded_at": row["recorded_at"], "value": row["value"], "unit": row["unit"]})
    return history
  finally:
    connection.close()


def prune_resource_metrics(older_than_minutes=15):
  cutoff = _cutoff(older_than_minutes)
  connection = get_connection()
  try:
    cursor = connection.execute("DELETE FROM resource_metrics WHERE recorded_at < ?", (cutoff,))
    connection.commit()
    return cursor.rowcount
  finally:
    connection.close()


def insert_threshold(resource_id, metric_name, normal_min, normal_max, warning_value, critical_value, comparison, unit=None):
  connection = get_connection()
  try:
    cursor = connection.execute("INSERT INTO thresholds (resource_id, metric_name, normal_min, normal_max, warning_value, critical_value, comparison, unit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (resource_id, metric_name, normal_min, normal_max, warning_value, critical_value, comparison, unit))
    connection.commit()
    return cursor.lastrowid
  finally:
    connection.close()


def get_thresholds(resource_id=None, metric_name=None):
  connection = get_connection()
  try:
    clauses, parameters = [], []
    if resource_id is not None:
      clauses.append("resource_id = ?")
      parameters.append(resource_id)
    if metric_name is not None:
      clauses.append("metric_name = ?")
      parameters.append(metric_name)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return _rows_to_dicts(connection.execute(f"SELECT * FROM thresholds{where} ORDER BY id", parameters))
  finally:
    connection.close()


def get_threshold(resource_id, metric_name):
  connection = get_connection()
  try:
    return _row_to_dict(connection.execute("SELECT * FROM thresholds WHERE resource_id = ? AND metric_name = ? ORDER BY id LIMIT 1", (resource_id, metric_name)).fetchone())
  finally:
    connection.close()


def insert_scenario(scenario_id, name, description, affected_resource_id, severity):
  connection = get_connection()
  try:
    cursor = connection.execute("INSERT INTO scenarios (id, name, description, affected_resource_id, severity) VALUES (?, ?, ?, ?, ?)", (scenario_id, name, description, affected_resource_id, severity))
    connection.commit()
    return cursor.lastrowid
  finally:
    connection.close()


def get_scenarios():
  connection = get_connection()
  try:
    return _rows_to_dicts(connection.execute("SELECT * FROM scenarios ORDER BY id"))
  finally:
    connection.close()


def get_scenario(id):
  connection = get_connection()
  try:
    return _row_to_dict(connection.execute("SELECT * FROM scenarios WHERE id = ?", (id,)).fetchone())
  finally:
    connection.close()


def insert_scenario_metric(scenario_id, resource_id, metric_name, injected_value, unit=None):
  connection = get_connection()
  try:
    cursor = connection.execute("INSERT INTO scenario_metrics (scenario_id, resource_id, metric_name, injected_value, unit) VALUES (?, ?, ?, ?, ?)", (scenario_id, resource_id, metric_name, injected_value, unit))
    connection.commit()
    return cursor.lastrowid
  finally:
    connection.close()


def get_scenario_metrics(scenario_id):
  connection = get_connection()
  try:
    return _rows_to_dicts(connection.execute("SELECT * FROM scenario_metrics WHERE scenario_id = ? ORDER BY id", (scenario_id,)))
  finally:
    connection.close()


def create_incident(scenario_id, resource_id, status="DETECTING"):
  connection = get_connection()
  try:
    connection.execute("UPDATE incidents SET is_active = 0 WHERE is_active = 1")
    cursor = connection.execute("INSERT INTO incidents (scenario_id, resource_id, status, is_active, detected_at) VALUES (?, ?, ?, 1, ?)", (scenario_id, resource_id, status, _now()))
    connection.commit()
    return cursor.lastrowid
  finally:
    connection.close()


def get_active_incident():
  connection = get_connection()
  try:
    return _row_to_dict(connection.execute("SELECT * FROM incidents WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone())
  finally:
    connection.close()


def get_incident(id):
  connection = get_connection()
  try:
    return _row_to_dict(connection.execute("SELECT * FROM incidents WHERE id = ?", (id,)).fetchone())
  finally:
    connection.close()


def get_incidents():
  connection = get_connection()
  try:
    return _rows_to_dicts(connection.execute("SELECT * FROM incidents ORDER BY id DESC"))
  finally:
    connection.close()


def update_incident_status(id, status):
  _update_incident_column(id, "status", status)


def update_incident_rca(id, rca_summary):
  _update_incident_column(id, "rca_summary", rca_summary)


def update_incident_ticket_draft(id, draft):
  _update_incident_column(id, "ticket_draft", draft)


def update_incident_ticket_final(id, final):
  _update_incident_column(id, "ticket_final", final)


def _update_incident_column(id, column, value):
  connection = get_connection()
  try:
    connection.execute(f"UPDATE incidents SET {column} = ? WHERE id = ?", (value, id))
    connection.commit()
  finally:
    connection.close()


def resolve_incident(id, servicenow_ticket_no=None):
  connection = get_connection()
  try:
    if servicenow_ticket_no is None:
      connection.execute("UPDATE incidents SET status = 'RESOLVED', resolved_at = ?, is_active = 0 WHERE id = ?", (_now(), id))
    else:
      connection.execute("UPDATE incidents SET status = 'RESOLVED', resolved_at = ?, is_active = 0, servicenow_ticket_no = ? WHERE id = ?", (_now(), servicenow_ticket_no, id))
    connection.commit()
  finally:
    connection.close()


def deactivate_incident(id):
  connection = get_connection()
  try:
    connection.execute("UPDATE incidents SET is_active = 0 WHERE id = ?", (id,))
    connection.commit()
  finally:
    connection.close()


def insert_incident_fix(incident_id, description, display_order):
  connection = get_connection()
  try:
    cursor = connection.execute("INSERT INTO incident_fixes (incident_id, description, display_order, is_selected) VALUES (?, ?, ?, 0)", (incident_id, description, display_order))
    connection.commit()
    return cursor.lastrowid
  finally:
    connection.close()


def get_incident_fixes(incident_id):
  connection = get_connection()
  try:
    return _rows_to_dicts(connection.execute("SELECT * FROM incident_fixes WHERE incident_id = ? ORDER BY display_order, id", (incident_id,)))
  finally:
    connection.close()


def select_incident_fix(fix_id):
  connection = get_connection()
  try:
    fix = connection.execute("SELECT incident_id FROM incident_fixes WHERE id = ?", (fix_id,)).fetchone()
    if fix is not None:
      connection.execute("UPDATE incident_fixes SET is_selected = 0 WHERE incident_id = ?", (fix["incident_id"],))
      connection.execute("UPDATE incident_fixes SET is_selected = 1 WHERE id = ?", (fix_id,))
    connection.commit()
  finally:
    connection.close()


def insert_agent_activity(incident_id, agent_name, message_type, message):
  connection = get_connection()
  try:
    cursor = connection.execute("INSERT INTO agent_activity (incident_id, agent_name, message_type, message, created_at) VALUES (?, ?, ?, ?, ?)", (incident_id, agent_name, message_type, message, _now()))
    connection.commit()
    return cursor.lastrowid
  finally:
    connection.close()


def get_agent_activity(incident_id=None):
  connection = get_connection()
  try:
    if incident_id is None:
      rows = connection.execute("SELECT * FROM agent_activity ORDER BY created_at, id")
    else:
      rows = connection.execute("SELECT * FROM agent_activity WHERE incident_id = ? ORDER BY created_at, id", (incident_id,))
    return _rows_to_dicts(rows)
  finally:
    connection.close()
