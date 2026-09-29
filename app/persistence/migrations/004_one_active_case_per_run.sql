-- At most one active (OPEN / UNDER_REVIEW) InvestigationCase per AnalysisRun.
-- A trigger rather than a partial UNIQUE index: databases created before this
-- migration may already hold duplicate active cases (double-submit), and a
-- unique index would fail to build on them. Existing rows are left untouched;
-- only new inserts are guarded. Case states never move back to active, so an
-- INSERT guard is sufficient.

CREATE INDEX IF NOT EXISTS idx_investigation_cases_run
    ON investigation_cases (analysis_run_id);

CREATE TRIGGER IF NOT EXISTS trg_investigation_cases_one_active_per_run
BEFORE INSERT ON investigation_cases
WHEN NEW.state IN ('OPEN', 'UNDER_REVIEW')
    AND EXISTS (
        SELECT 1 FROM investigation_cases
        WHERE analysis_run_id = NEW.analysis_run_id
          AND state IN ('OPEN', 'UNDER_REVIEW')
    )
BEGIN
    SELECT RAISE(ABORT, 'UNIQUE constraint failed: one active investigation case per analysis run');
END;
