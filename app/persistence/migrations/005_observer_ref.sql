-- Pseudonymous per-browser observer reference (SHA-256 of the cookie token with
-- a domain-separation prefix; the token itself is never stored). Nullable and
-- additive: packets created before this migration keep NULL and display as
-- "Observer unknown (pre-pseudonym)". Kept outside document_json so packet
-- documents, confirmation content hashes, and FHIR mapping are unchanged.

ALTER TABLE observation_packets ADD COLUMN observer_ref TEXT;
