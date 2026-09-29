-- PostgreSQL mirror of ../004_one_active_case_per_run.sql.
-- At most one active (OPEN / UNDER_REVIEW) InvestigationCase per AnalysisRun.
-- SQLite uses a BEFORE INSERT trigger only because pre-existing SQLite files
-- may hold legacy duplicates. PostgreSQL databases start empty under this
-- schema, so a partial UNIQUE index enforces the same rule. It also guards
-- UPDATEs, which is equivalent because case states never move back to active.
-- A violation surfaces as a unique-constraint IntegrityError, as the trigger does.

CREATE INDEX IF NOT EXISTS idx_investigation_cases_run
    ON investigation_cases (analysis_run_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_investigation_cases_one_active_per_run
    ON investigation_cases (analysis_run_id)
    WHERE state IN ('OPEN', 'UNDER_REVIEW');
