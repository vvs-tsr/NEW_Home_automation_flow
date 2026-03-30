-- schema.sql
-- Jarvis EchoBud database schema.
-- Run once to initialise: sqlite3 memory/echobud.db < memory/schema.sql
-- All CREATE TABLE statements use IF NOT EXISTS — safe to re-run.

-- ── Events ───────────────────────────────────────────────────────────────────
-- General event log fed from the MQTT stream (all sources).
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       INTEGER NOT NULL,          -- Unix epoch seconds
    source          TEXT    NOT NULL,          -- e.g. vision, ha, nodemcu, jarvis
    event_type      TEXT    NOT NULL,          -- e.g. object_detected, state_change
    payload         TEXT    NOT NULL,          -- Full JSON payload as string
    raw_mqtt_topic  TEXT    DEFAULT ''         -- Original MQTT topic for tracing
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp);
CREATE INDEX IF NOT EXISTS idx_events_source    ON events (source);

-- ── Actions ──────────────────────────────────────────────────────────────────
-- Log of actions taken by Jarvis (MQTT commands sent, routines run, etc.)
CREATE TABLE IF NOT EXISTS actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       INTEGER NOT NULL,
    triggered_by    TEXT    NOT NULL,          -- e.g. llm, routine, user_voice
    action_type     TEXT    NOT NULL,          -- e.g. mqtt_publish, run_routine
    target          TEXT    NOT NULL,          -- e.g. MQTT topic or routine name
    payload         TEXT    NOT NULL,          -- Command payload or routine args as JSON
    success         INTEGER NOT NULL DEFAULT 1 -- 1 = success, 0 = failure
);

CREATE INDEX IF NOT EXISTS idx_actions_timestamp ON actions (timestamp);

-- ── Alerts ───────────────────────────────────────────────────────────────────
-- Security alerts from the YOLO camera pipeline.
CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       INTEGER NOT NULL,
    source          TEXT    NOT NULL,          -- e.g. vision
    threat_class    TEXT    NOT NULL,          -- e.g. person, car, dog
    confidence      REAL    NOT NULL,          -- 0.0 – 1.0
    location        TEXT    DEFAULT '',        -- e.g. front_door, driveway
    acknowledged    INTEGER NOT NULL DEFAULT 0 -- 0 = new, 1 = acknowledged
);

CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts (timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_class     ON alerts (threat_class);

-- ── Conversations ─────────────────────────────────────────────────────────────
-- Full conversation history for each voice session.
CREATE TABLE IF NOT EXISTS conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT    NOT NULL,          -- UUID per session
    timestamp       INTEGER NOT NULL,
    role            TEXT    NOT NULL,          -- system, user, assistant, tool
    content         TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations (session_id);
