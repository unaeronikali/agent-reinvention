-- NorthStar Retail Digital Twin -- SQLite schema
-- 9-table data model per others/txt/requirements.txt (Data Model section, lines ~166-267).
-- This file is the single source of truth for table shape. db.py builds the DB from this file.
--
-- Design principle (frozen, GATE A): the seed script writes RAW metric values only.
-- is_anomaly is NEVER set by seed.py -- it stays NULL until the Web App Executor writes
-- 0/1 based on the Detect Agent's decision. There is no `priority` column on incidents;
-- priority is derived from scenarios.severity (P1/P2/P3) -- review #5.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS agent_activity;
DROP TABLE IF EXISTS incident_fixes;
DROP TABLE IF EXISTS incidents;
DROP TABLE IF EXISTS scenario_metrics;
DROP TABLE IF EXISTS scenarios;
DROP TABLE IF EXISTS thresholds;
DROP TABLE IF EXISTS resource_metrics;
DROP TABLE IF EXISTS resources;
DROP TABLE IF EXISTS resource_groups;

-- Table 1: resource_groups
CREATE TABLE resource_groups (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,          -- e.g. rg-prod-app
    description     TEXT                           -- e.g. Application Tier
);

-- Table 2: resources
CREATE TABLE resources (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_group_id   INTEGER NOT NULL REFERENCES resource_groups(id),
    name                TEXT NOT NULL UNIQUE,       -- e.g. webapp-northstar
    type                TEXT NOT NULL,              -- WebApp, FunctionApp, APIManagement, SQLDatabase,
                                                     -- CosmosDB, KeyVault, StorageAccount, VirtualMachine
    display_name        TEXT,                       -- e.g. Customer Storefront
    icon                TEXT,                       -- emoji / icon name for UI
    status              TEXT NOT NULL DEFAULT 'Healthy',  -- Healthy / Degraded / Critical
    status_updated_at   DATETIME                    -- enables "Degraded since ..." in UI   [review #7]
);

-- Table 3: resource_metrics (time-series -- main seeded table)
CREATE TABLE resource_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id     INTEGER NOT NULL REFERENCES resources(id),
    metric_name     TEXT NOT NULL,      -- response_time_ms, cpu_pct, memory_pct, error_rate_pct,
                                         -- request_count, connection_count
    value           REAL NOT NULL,
    unit            TEXT,               -- ms, %, count
    recorded_at     DATETIME NOT NULL,
    is_anomaly      INTEGER             -- NULL = not yet evaluated (default). The Detect Agent
                                         -- DECIDES; the Web App Executor WRITES 0/1 based on that
                                         -- decision (agents cannot touch the DB). Seed script never
                                         -- sets this column.                                [review #9]
);

-- Table 4: thresholds
CREATE TABLE thresholds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id     INTEGER NOT NULL REFERENCES resources(id),
    metric_name     TEXT NOT NULL,
    normal_min      REAL,               -- healthy range floor -- used by seed --mode normal  [review #6]
    normal_max      REAL,               -- healthy range ceiling -- used by seed --mode normal [review #6]
    warning_value   REAL,
    critical_value  REAL,
    comparison      TEXT,               -- gt (high is bad) / lt (low is bad)
    unit            TEXT
);

-- Table 5: scenarios
CREATE TABLE scenarios (
    id                      INTEGER PRIMARY KEY,   -- 1-5, assigned explicitly (not autoincrement)
    name                    TEXT NOT NULL,          -- e.g. Black Friday Surge
    description             TEXT,
    affected_resource_id    INTEGER NOT NULL REFERENCES resources(id),
    severity                TEXT NOT NULL           -- P1 / P2 / P3 (single source of truth for priority) [review #5]
);

-- Table 6: scenario_metrics
CREATE TABLE scenario_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id     INTEGER NOT NULL REFERENCES scenarios(id),
    resource_id     INTEGER NOT NULL REFERENCES resources(id),  -- usually = scenario's affected resource [review #1]
    metric_name     TEXT NOT NULL,
    injected_value  REAL NOT NULL,      -- the anomalous value the seed script writes
    unit            TEXT                -- avoids join dependency at seed time                 [review #10]
);

-- Table 7: incidents (single active incident at a time)
CREATE TABLE incidents (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id             INTEGER NOT NULL REFERENCES scenarios(id),
    resource_id             INTEGER NOT NULL REFERENCES resources(id),
    status                  TEXT NOT NULL DEFAULT 'DETECTING',
                            -- DETECTING -> ANALYZING -> DIAGNOSING -> AWAITING_FIX_APPROVAL
                            -- -> FIXING -> AWAITING_TICKET_APPROVAL -> RESOLVED
    is_active               INTEGER NOT NULL DEFAULT 1,  -- 1 = the current open incident;
                                                          -- app enforces one at a time      [review #4]
    detected_at             DATETIME NOT NULL,
    resolved_at             DATETIME,               -- nullable
    rca_summary             TEXT,                   -- nullable -- filled by RCA Agent
    ticket_draft            TEXT,                   -- nullable -- AI-drafted description (Ticket Agent)
    ticket_final            TEXT,                   -- nullable -- human-edited version at HITL #2
    servicenow_ticket_no    TEXT                    -- nullable -- e.g. INC0001234
    -- (priority intentionally dropped -- derived from scenarios.severity)                    [review #5]
);

-- Table 8: incident_fixes (replaces brittle JSON blob for HITL #1)                            [review #3]
CREATE TABLE incident_fixes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id     INTEGER NOT NULL REFERENCES incidents(id),
    description     TEXT NOT NULL,      -- one proposed fix option (from Suggest Agent)
    display_order   INTEGER,            -- order shown in HITL panel
    is_selected     INTEGER DEFAULT 0   -- 1 = option the human chose at HITL #1
);

-- Table 9: agent_activity (feeds the Activity Log terminal)
CREATE TABLE agent_activity (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id     INTEGER REFERENCES incidents(id),
    agent_name      TEXT NOT NULL,      -- Orchestrator, Detect, Analyze, RCA, Suggest, Fix, Ticket, Human
    message_type    TEXT NOT NULL,      -- INFO / WARNING / ERROR / HUMAN -- drives log color-coding [review #8]
    message         TEXT NOT NULL,      -- text shown in the terminal log
    created_at      DATETIME NOT NULL
);

-- Relationships (documented, enforced via FKs above):
--   resource_groups --< resources --< resource_metrics
--                                  --< thresholds
--   scenarios --< scenario_metrics
--             --< incidents --< incident_fixes
--                           --< agent_activity
--   resources --< incidents

CREATE INDEX idx_resources_rg ON resources(resource_group_id);
CREATE INDEX idx_metrics_resource ON resource_metrics(resource_id, metric_name);
CREATE INDEX idx_metrics_recorded_at ON resource_metrics(recorded_at);
CREATE INDEX idx_thresholds_resource ON thresholds(resource_id, metric_name);
CREATE INDEX idx_scenario_metrics_scenario ON scenario_metrics(scenario_id);
CREATE INDEX idx_incidents_active ON incidents(is_active);
CREATE INDEX idx_incident_fixes_incident ON incident_fixes(incident_id);
CREATE INDEX idx_agent_activity_incident ON agent_activity(incident_id);
