-- ConfirmGate schema v1 — storage integrity only; domain owns business rules.
-- Opaque packet_id TEXT PRIMARY KEY (UUID hex). No sequential scraping ids.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY NOT NULL,
    applied_at TEXT NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observation_packets (
    packet_id TEXT PRIMARY KEY NOT NULL,
    site_ref_id TEXT NOT NULL,
    city TEXT NOT NULL,
    workflow_state TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    document_json TEXT NOT NULL,
    flags_rules_version TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_packets_site_ref
    ON observation_packets (site_ref_id);

CREATE INDEX IF NOT EXISTS idx_packets_workflow
    ON observation_packets (workflow_state);

-- Append-only provenance. No UPDATE/DELETE API in application.
CREATE TABLE IF NOT EXISTS provenance_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    packet_id TEXT NOT NULL,
    at TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    model_id TEXT,
    prompt_version TEXT,
    rule_engine_version TEXT,
    FOREIGN KEY (packet_id) REFERENCES observation_packets (packet_id)
);

CREATE INDEX IF NOT EXISTS idx_provenance_packet_seq
    ON provenance_events (packet_id, seq);
