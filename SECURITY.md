# Security

## Deployment boundary

This is a **hackathon demo**, not a multi-user production service.

- **No authentication or authorization.** Anyone who can reach the URL can submit, confirm, finalize, analyze, open cases, and record decisions.
- **One shared reviewer identity.** Every reviewer action is attributed to `demo-reviewer`. Audit records show *what* happened and *when*, not *which person* acted.
- **No CSRF protection or rate limiting.** Do not expose the app with real personal data.
- **Single instance, single SQLite file.** Back up the `/data` volume if you care about the demo data. Data is not encrypted at rest.
- **Photos are not stored.** Only the uploaded file name is recorded. Request bodies above `MAX_UPLOAD_BYTES` (default 10 MB) are refused with HTTP 413.
- **Synthetic data.** The AquaSignal seed fixtures are synthetic and labelled as such.
- **Demo reset.** With `DEMO_MODE=true`, the operator can restore the seeded dataset with `python -m app.demo.reset` (or on start with `DEMO_RESET_ON_START=true`). This wipes all visitor data. It is a shell command only, with no HTTP endpoint, and it refuses to run when `DEMO_MODE` is not enabled. Reset limits how long vandalised data stays visible. It does not stop anyone from submitting or deciding between resets.

Do not enter personal, health, or sensitive location data into a public deployment.

## Observer handles

- Each browser receives a first-party `cg_observer` cookie holding a random token (HttpOnly, SameSite=Lax, one year). The app stores only a one-way hash of it and shows a short handle such as `Observer-3F9A01C2`. The raw token is not stored, logged, or displayed.
- The handle helps reviewers distinguish contributors. It is **not** a verified identity or authentication: clearing cookies or switching browsers gives a new handle, and anyone with the cookie can submit under that handle.
- Observations created before this feature show `Observer unknown (pre-pseudonym)`. Synthetic seed rows show `Synthetic fixture`.
- Handles are excluded from FHIR exports and from analysis snapshot and parameters hashes.
- **HTTPS.** The cookie is marked `Secure` only when the app sees the request as `https`. Behind a TLS-terminating proxy this depends on uvicorn's proxy-header handling. The shipped `Dockerfile` runs `uvicorn ... --proxy-headers --forwarded-allow-ips='*'`, which trusts `X-Forwarded-Proto` from any peer. This **assumes the container is reachable only through a trusted reverse proxy** and is not safe in general: if the container port is exposed directly, clients can spoof the scheme. When the port is exposed, set `--forwarded-allow-ips` to the proxy address. This setup is not a production security review.

## Secrets

- Configuration comes only from environment variables (see [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)). `.env` is git-ignored.
- AI is off by default. If enabled, the API key is sent only to the configured `AI_BASE_URL`. It is never logged, stored in provenance, or shown in `/healthz`.
- Sending observation text to a third-party AI provider is a data-sharing decision for whoever deploys the app.

## Reporting an issue

Please open a GitHub issue for non-sensitive problems. For anything sensitive, such as an exposed secret or a way to corrupt or forge audit records, email the maintainer through the address on the GitHub profile, or use GitHub private vulnerability reporting if it is enabled. Do not include exploit details in public issues.

## Known limitations

- The authority model (who may confirm, finalize, or decide) is enforced in the application layer but is not tied to authenticated users.
- `HumanDecision` records are stored in their own tables and are not copied into the ConfirmGate packet provenance.
- The FHIR export covers a subset of the OAH IG. It was validated at release time against the CI-build IG compiled from FSH (0 errors; see [`docs/FHIR-SPEC.md`](docs/FHIR-SPEC.md) §9.1), but the running app does not validate each export and no published OAH package exists yet.
