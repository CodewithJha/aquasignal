-- PostgreSQL mirror of ../005_observer_ref.sql.

ALTER TABLE observation_packets ADD COLUMN IF NOT EXISTS observer_ref TEXT COLLATE "C";
