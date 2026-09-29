-- PostgreSQL mirror of ../003_a6_hardening.sql.

ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS site_id TEXT COLLATE "C" NOT NULL DEFAULT '';
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS window_start TEXT COLLATE "C";
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS window_end TEXT COLLATE "C";

CREATE INDEX IF NOT EXISTS idx_analysis_runs_site_id
    ON analysis_runs (site_id);

ALTER TABLE evidence_items ADD COLUMN IF NOT EXISTS fields_json TEXT NOT NULL DEFAULT '{}';
