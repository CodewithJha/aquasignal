-- AquaSignal Phase A6 — self-describing AnalysisRun scope + normalized evidence fields.
-- Additive only; existing rows get empty defaults (brief falls back where needed).

ALTER TABLE analysis_runs ADD COLUMN site_id TEXT NOT NULL DEFAULT '';
ALTER TABLE analysis_runs ADD COLUMN window_start TEXT;
ALTER TABLE analysis_runs ADD COLUMN window_end TEXT;

CREATE INDEX IF NOT EXISTS idx_analysis_runs_site_id
    ON analysis_runs (site_id);

ALTER TABLE evidence_items ADD COLUMN fields_json TEXT NOT NULL DEFAULT '{}';
