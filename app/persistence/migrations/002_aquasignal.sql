-- AquaSignal Phase A2 — snapshots / runs / signals / relations / cases.
-- ConfirmGate tables (observation_packets, provenance_events) unchanged.
-- Storage integrity only; domain owns business rules.

CREATE TABLE IF NOT EXISTS evidence_items (
    evidence_id TEXT PRIMARY KEY NOT NULL,
    source_class TEXT NOT NULL,
    site_id TEXT NOT NULL,
    city TEXT NOT NULL,
    display_name TEXT NOT NULL,
    lat REAL,
    lon REAL,
    fhir_location_identifier TEXT,
    observed_at TEXT NOT NULL,
    payload_ref TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    license_tag TEXT NOT NULL,
    is_synthetic INTEGER NOT NULL CHECK (is_synthetic IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_evidence_items_site
    ON evidence_items (site_id);

CREATE TABLE IF NOT EXISTS evidence_snapshots (
    snapshot_id TEXT PRIMARY KEY NOT NULL,
    snapshot_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    source_manifest_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_snapshots_hash
    ON evidence_snapshots (snapshot_hash);

-- Ordered membership (relational; not a JSON blob of relationships).
CREATE TABLE IF NOT EXISTS evidence_snapshot_members (
    snapshot_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    evidence_id TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, position),
    FOREIGN KEY (snapshot_id) REFERENCES evidence_snapshots (snapshot_id),
    FOREIGN KEY (evidence_id) REFERENCES evidence_items (evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_members_evidence
    ON evidence_snapshot_members (evidence_id);

CREATE TABLE IF NOT EXISTS analysis_runs (
    run_id TEXT PRIMARY KEY NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    detector_set_version TEXT NOT NULL,
    parameters_hash TEXT NOT NULL,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_snapshot_hash
    ON analysis_runs (snapshot_hash);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_status
    ON analysis_runs (status);

CREATE TABLE IF NOT EXISTS analysis_run_signals (
    run_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    signal_id TEXT NOT NULL,
    PRIMARY KEY (run_id, position),
    FOREIGN KEY (run_id) REFERENCES analysis_runs (run_id)
);

CREATE INDEX IF NOT EXISTS idx_analysis_run_signals_signal
    ON analysis_run_signals (signal_id);

CREATE TABLE IF NOT EXISTS evidence_relations (
    relation_id TEXT PRIMARY KEY NOT NULL,
    relation_type TEXT NOT NULL,
    left_ref TEXT NOT NULL,
    right_ref TEXT NOT NULL,
    analysis_run_id TEXT NOT NULL,
    rationale_code TEXT NOT NULL,
    message TEXT NOT NULL,
    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs (run_id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_relations_run
    ON evidence_relations (analysis_run_id);

CREATE TABLE IF NOT EXISTS environmental_signals (
    signal_id TEXT PRIMARY KEY NOT NULL,
    detector_id TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    site_id TEXT NOT NULL,
    city TEXT NOT NULL,
    display_name TEXT NOT NULL,
    lat REAL,
    lon REAL,
    fhir_location_identifier TEXT,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    summary TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    explanation_json TEXT NOT NULL,
    analysis_run_id TEXT NOT NULL,
    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs (run_id)
);

CREATE INDEX IF NOT EXISTS idx_environmental_signals_run
    ON environmental_signals (analysis_run_id);

CREATE INDEX IF NOT EXISTS idx_environmental_signals_site
    ON environmental_signals (site_id);

CREATE TABLE IF NOT EXISTS signal_evidence (
    signal_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    evidence_id TEXT NOT NULL,
    PRIMARY KEY (signal_id, position),
    FOREIGN KEY (signal_id) REFERENCES environmental_signals (signal_id),
    FOREIGN KEY (evidence_id) REFERENCES evidence_items (evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_signal_evidence_evidence
    ON signal_evidence (evidence_id);

CREATE TABLE IF NOT EXISTS investigation_cases (
    case_id TEXT PRIMARY KEY NOT NULL,
    site_id TEXT NOT NULL,
    city TEXT NOT NULL,
    display_name TEXT NOT NULL,
    lat REAL,
    lon REAL,
    fhir_location_identifier TEXT,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    analysis_run_id TEXT NOT NULL,
    reproducibility_ref TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    state TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs (run_id)
);

CREATE INDEX IF NOT EXISTS idx_investigation_cases_site
    ON investigation_cases (site_id);

CREATE INDEX IF NOT EXISTS idx_investigation_cases_state
    ON investigation_cases (state);

CREATE TABLE IF NOT EXISTS case_signals (
    case_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    signal_id TEXT NOT NULL,
    PRIMARY KEY (case_id, position),
    FOREIGN KEY (case_id) REFERENCES investigation_cases (case_id),
    FOREIGN KEY (signal_id) REFERENCES environmental_signals (signal_id)
);

CREATE INDEX IF NOT EXISTS idx_case_signals_signal
    ON case_signals (signal_id);

CREATE TABLE IF NOT EXISTS human_decisions (
    decision_id TEXT PRIMARY KEY NOT NULL,
    case_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    decision_code TEXT NOT NULL,
    rationale TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES investigation_cases (case_id)
);

CREATE INDEX IF NOT EXISTS idx_human_decisions_case
    ON human_decisions (case_id);

CREATE TABLE IF NOT EXISTS case_decisions (
    case_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    decision_id TEXT NOT NULL,
    PRIMARY KEY (case_id, position),
    FOREIGN KEY (case_id) REFERENCES investigation_cases (case_id),
    FOREIGN KEY (decision_id) REFERENCES human_decisions (decision_id)
);

CREATE TABLE IF NOT EXISTS decision_signals (
    decision_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    signal_id TEXT NOT NULL,
    PRIMARY KEY (decision_id, position),
    FOREIGN KEY (decision_id) REFERENCES human_decisions (decision_id)
);

CREATE INDEX IF NOT EXISTS idx_decision_signals_signal
    ON decision_signals (signal_id);
