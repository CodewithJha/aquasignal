# ConfirmGate + AquaSignal

Track 3 (AI-Supported Assessment) entry for the [OneAquaHealth IEEE Global Hackathon](https://oneaquahealth-ieee-hackathon.devpost.com/): an **observation-integrity** web app for citizen stream observations in the five OneAquaHealth cities (Coimbra, Benevento, Ghent, Oslo, Toulouse).

**Problem.** Citizen stream reports are inconsistent, so they are hard to reuse for One Health work. **Approach.** Deterministic quality checks, a mandatory human confirmation step, FHIR export only after a human finalizes, and a site investigation brief built from reproducible, deterministic detectors. AI is optional and advisory only.

Live URL: **https://aquasignal.onrender.com** (Render Free; the first request after ~15 min idle takes about a minute while the instance wakes, and each wake restores the seeded demo data). Submission deadline: 4 Oct 2026, 9:00 PM PDT (5 Oct 2026, 09:30 IST).

## What it does

**ConfirmGate: one observation, from submission to authority**

1. A citizen submits protocol-lite fields (a subset of the OAH field protocol) for one city. They can attach a photo, but the app records **only the file name**. The image is neither stored nor analyzed.
2. A deterministic **FlagEngine** raises structured quality flags such as missing fields, vocabulary problems, or possible duplicates. There is no trust score.
3. A human **confirms or edits** the observation, then **finalizes** it. The demo reviewer desk at `/review` can accept, edit, or reject.
4. Only a `FINALIZED` observation can be exported as FHIR. Every state change goes into an append-only provenance log.

**AquaSignal: site investigation from finalized evidence**

- On `/investigate/sites/{site}`, a human presses **Analyze finalized observations**. The system freezes a snapshot of that site's `FINALIZED` observations and runs two deterministic detectors:
  - `temporal_baseline_shift` (v1) compares recent ordinal values (for example `foam`) with a baseline window using median and MAD (median absolute deviation). When MAD is zero, it uses a fixed threshold of one vocabulary step.
  - `cross_observation_contradiction` (v2) compares pairs of observations recorded within 24 hours of each other (same visit) and marks each shared protocol field as supporting, conflicting, or duplicate. Identical observations within 10 minutes count as one duplicate submission. Observations further apart are not compared.
- The output is a **Site Investigation Brief** with evidence, signals, conflicts, insufficient-evidence states, and reproducibility data. A signal is an **evidence pattern that deserves human investigation**. It is not a finding about the water.
- A human can **open an investigation case** and **record a decision**: note, request more evidence, close as insufficient, close as change suspected, or dismiss. Each decision is attributed to the demo reviewer identity.

**FHIR export.** `/fhir` exports a Bundle containing a `Location` and `Observation` resources shaped to the OAH CI-build profiles (FHIR R4, verified TemporaryOahSystem subset only). `Observation.status` is always `final`. The exporter refuses any observation that is not `FINALIZED` and never emits `preliminary`. It covers a **subset** of the IG (Location + simple indicator Observations). Release validation with the HL7 FHIR Validator 6.10.4 against the `hl7-eu/oah` CI-build IG (compiled from FSH at commit `b907cf0`, since no built OAH package is published) gave **0 errors and 5 best-practice warnings** (missing narrative) per Bundle; the running app does not re-validate each export. The Bundle contains no FHIR `Provenance` resource because the app keeps provenance in its own append-only log. Details: [`docs/FHIR-SPEC.md`](docs/FHIR-SPEC.md).

**AI (optional, off by default).** AI is text-only and advisory. It can:
- suggest values for **empty** enum fields, using only the allowed vocabulary
- rephrase deterministic flag messages in plain language
- restate an investigation brief and its signals

It does **not**:
- look at images
- claim anything about pollution, contamination, pathogens, disease, health risk, or water safety
- confirm, finalize, change signals, or decide cases

Suggestions become part of an observation only after a human accepts them. With `AI_PROVIDER=null` (the default), the app runs without a network or an API key, and the brief shows "AI advisory: disabled. Deterministic analysis is complete without it." Policy: [`docs/AI-POLICY.md`](docs/AI-POLICY.md).

## Known limitations

- **Synthetic fixtures.** The demo seed script loads 29 hand-made rows for Coimbra from four fixtures under `app/demo/aquasignal/`: `A_temporal_shift`, `C_contradiction`, `E_insufficient`, and `B_stable_control`. A fifth fixture, `D_duplicate_support` (3 rows), is not seeded. The UI labels all of them **SYNTHETIC FIXTURE**. None of this is real monitoring data.
- **City-centroid coordinates.** Sites use city-centre coordinates for FHIR `Location`. They are demo positions, not sampling stations.
- **Synonym canonicalization.** Detectors see canonicalized values (`none`→`absent`, `gray`→`grey`, and yes/no-style values), and the original values are kept. Because of this, fixture B shows **no** contradiction and no temporal shift.
- **Temporal shift is shown only on synthetic fixtures.** Real submissions made during the hackathon cannot build a long enough baseline to trigger it, and the fixture runs use a looser threshold than the Analyze button. Real visits produce contradiction or insufficient-evidence results. The run history labels each run **SYNTHETIC FIXTURE**, **FINALIZED OBSERVATIONS**, or **MIXED**.
- **Duplicate-warning noise.** Every submission after the first for a city gets a "possible duplicate" flag.
- **AI claim filter is a regex screen.** In an internal test it let through most new phrasings of forbidden claims (for example "the river is healthy"). The AI `notes` field is not screened and appears in the JSON API. Keep `AI_PROVIDER=null` for demos.
- **Hung AI provider slows submit.** If an external AI endpoint hangs, a submission can take about 2× `AI_TIMEOUT` before the app continues without AI. With `AI_PROVIDER=null` there is no delay.
- **AI audit gaps.** The audit log records an AI-suggestion event on every packet even when AI is off. The investigation AI advisory is re-requested on each page view and is never saved or audited.
- **Observer handles are not identities.** Each browser gets a readable handle such as `Observer-3F9A01C2` so reviewers can tell contributors apart on an observation, in the reviewer desk, and in investigation evidence. It comes from a browser cookie, not a login: clearing cookies or using another browser gives the same person a new handle, and two people can (rarely) share one. Observations made before this feature show **Observer unknown (pre-pseudonym)**; seeded rows show **Synthetic fixture**. Handles are not included in FHIR exports or analysis hashes.
- **No authentication and no CSRF protection.** There is one shared demo reviewer identity. This is a demo, not a multi-user production service. See [`SECURITY.md`](SECURITY.md).

## Reproducibility

Every analysis run stores:
- a **snapshot hash** of the frozen evidence manifest, which includes the vocabulary canonicalization version `vocab-canon@1`
- a **parameters hash**
- the **detector set version** `aquasignal-detectors-a3-v2`

Analysis windows are derived from evidence timestamps, never from the wall clock, so the same evidence produces the same hashes. Runs are append-only and are never overwritten. The hashes are shown on the brief and at `GET /api/analyses/{run_id}/reproducibility`.

## Run locally

Requires Python 3.12 or newer. CI tests 3.12, 3.13, and 3.14.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # runtime only
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000. The SQLite schema is created and migrated automatically on first start, at `data/confirmgate.sqlite3` unless you set `DATABASE_URL`. AI is off unless you configure it. See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) and [`.env.example`](.env.example).

| Path | Purpose |
|---|---|
| `/upload` | Submit an observation (city, protocol-lite fields, optional photo file name, notes) |
| `/observation/{id}` | Flags, corrections, confirm, finalize |
| `/review` | Demo reviewer desk |
| `/fhir` | FHIR Bundle, available only after `FINALIZED` |
| `/investigate` | AquaSignal site briefs, Analyze button, cases, human decisions |
| `/healthz` | Liveness and database reachability (JSON) |

### Tests

```bash
pip install -r requirements-dev.txt
pytest
```

To run the same suite against PostgreSQL (each test gets its own schema; the few tests that inspect the SQLite file are skipped):

```bash
docker run -d --name aq-pg -e POSTGRES_PASSWORD=<local-password> -p 55432:5432 postgres:16
TEST_DATABASE_URL=postgresql://postgres:<local-password>@127.0.0.1:55432/postgres pytest
```

### Demo

```bash
python scripts/seed_aquasignal_demo.py   # optional: labelled synthetic Coimbra runs
uvicorn app.main:app --port 8000
```

Full walkthrough: [`docs/DEMO.md`](docs/DEMO.md). The path is submit → confirm → finalize → **Analyze finalized observations** → brief → open case → **record human decision** → AI advisory (unavailable when AI is off) → FHIR.

### Docker

```bash
docker build -t confirmgate .
docker run --rm -p 8000:8000 -v confirmgate-data:/data -e AI_PROVIDER=null confirmgate
# optional seed inside the running container:
docker exec <container> python scripts/seed_aquasignal_demo.py
```

The image runs as a non-root user. It stores SQLite at `/data/confirmgate.sqlite3` (mount a volume there), honors `PORT`, has `AI_PROVIDER=null` by default, and includes a `HEALTHCHECK` against `/healthz`.

### Deploy

Any container host that builds from the `Dockerfile` works. The app does not need any secret to start.

- Mount a **persistent volume at `/data`**. Without one, observations, runs, cases, and decisions are lost on restart.
- Let the host set `PORT` if it requires that. The container listens on `${PORT}` (default 8000).
- Set the health check path to **`/healthz`**. It returns HTTP 200 `{"status":"ok","database":"ok"}`, or HTTP 503 if the database is unreachable.
- Run **one instance only**, because SQLite lives on a single volume.
- Leave `AI_PROVIDER=null` unless you want optional AI. See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).
- **HTTPS and the observer cookie.** The `cg_observer` cookie gets the `Secure` flag only when the app sees the request as `https`. Behind a TLS-terminating proxy, that depends on uvicorn trusting the proxy's `X-Forwarded-Proto` header. The shipped `Dockerfile` runs uvicorn with `--proxy-headers --forwarded-allow-ips='*'`, so it trusts forwarded headers from any peer. This assumes the container is reachable only through a trusted reverse proxy; it is not safe in general. If the container port is exposed directly, clients can spoof the scheme; narrow `--forwarded-allow-ips` to your proxy's address. See [`SECURITY.md`](SECURITY.md).
- For a public demo, set `DEMO_MODE=true` and `DEMO_RESET_ON_START=true` in the host's environment settings (they are not baked into the image). Every restart then restores the seeded dataset.
- Instead of a volume, you can point `DATABASE_URL` at PostgreSQL (`postgres://…` or `postgresql://…`). Migrations for PostgreSQL live in `app/persistence/migrations/postgres/` and run on start, like the SQLite ones.

### Render (the live demo)

[`render.yaml`](render.yaml) is a Render Blueprint: a **Free web service** built from the `Dockerfile` (Frankfurt, health check `/healthz`, auto-deploy from `main`) plus a **Free Render Postgres 16** database whose internal connection string is injected as `DATABASE_URL`. All state is in PostgreSQL, since the free instance's filesystem is ephemeral. The service sets `DEMO_MODE=true`, `DEMO_RESET_ON_START=true`, and `AI_PROVIDER=null`; the code defaults stay off.

- **Cold starts.** Render spins a free service down after 15 minutes without traffic. The next request waits about a minute, and startup restores the seeded dataset, so visitor data does not survive an idle period. The app has no "seed only if empty" mode, so this is the reset mechanism for the demo.
- **Manual reset.** Free services have no shell. Either restart or redeploy the service from the Render dashboard (the startup reset runs), or run the reset locally against the database's external connection string after adding your IP to the database's access-control list (it allows no external IPs by default): `DEMO_MODE=true DATABASE_URL='<external connection string>' python -m app.demo.reset`.
- **Free Postgres expiry.** Render deletes free databases 30 days after creation (with a 14-day grace period to upgrade). The demo database was created on 29 Sep 2026 and expires on **29 Oct 2026**, after judging (5–15 Oct) and the winners' announcement (24 Oct).
- **Forwarded headers.** Render's proxy is the only way into a web service and terminates TLS, so trusting `X-Forwarded-Proto` there is correct: the observer cookie is sent with `Secure` over HTTPS.

### Public demo behavior

- The public demo runs on **seeded demonstration data**: the synthetic Coimbra AquaSignal runs, labelled **SYNTHETIC FIXTURE** wherever they appear. Anything not labelled that way was submitted by a visitor.
- The data **may be reset periodically** to that seeded state. Submissions, confirmations, cases, and decisions made by visitors are removed on reset.
- It is **not a production multi-user deployment** and is **not protected by authentication**. Between resets, anyone can submit, confirm, finalize, analyze, open cases, and record decisions. Do not enter personal or sensitive data.
- The reset exists for reproducibility. After a reset, the seeded runs have the same snapshot and parameters hashes every time.

Reset is off unless the operator enables it. There is no HTTP reset endpoint.

| Variable | Default | Effect |
|---|---|---|
| `DEMO_MODE` | `false` | Enables the reset command and shows a "Public demo — data may be reset" note. When it is `false`, nothing is ever reset. |
| `DEMO_RESET_ON_START` | `false` | Resets on app start. Only takes effect when `DEMO_MODE=true` too. |

Reset command (no arguments; it only touches the database in `DATABASE_URL` and refuses to run unless `DEMO_MODE=true`):

```bash
DEMO_MODE=true python -m app.demo.reset
# in Docker, if DEMO_MODE=true is already set on the container:
docker exec <container> python -m app.demo.reset
```

The reset applies any pending migrations, deletes all data rows in a single transaction (the migration table is kept), then re-seeds the synthetic fixtures. It edits the SQLite file in place and never swaps the file (on PostgreSQL it runs one `TRUNCATE … RESTART IDENTITY`), so it is safe to run while the server is up. Requests made during the sub-second gap between the delete and the re-seed may briefly see an empty dataset.

Scheduled reset: use your platform's scheduled job, or a host crontab entry. The app has no scheduler of its own. For example, to reset every day at 03:00 UTC:

```cron
0 3 * * * docker exec <container> python -m app.demo.reset
```

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): module map, runtime flow, dependency rules
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md): environment variables
- [`docs/DEMO.md`](docs/DEMO.md): demo script
- [`docs/HITL-POLICY.md`](docs/HITL-POLICY.md), [`docs/AI-POLICY.md`](docs/AI-POLICY.md), [`docs/FHIR-SPEC.md`](docs/FHIR-SPEC.md), [`docs/SIGNAL-ENGINE.md`](docs/SIGNAL-ENGINE.md)
- Design records: [`docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md`](docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md), [`docs/AQUASIGNAL-ARCHITECTURE-SPIKE.md`](docs/AQUASIGNAL-ARCHITECTURE-SPIKE.md). Index, including superseded internal notes: [`docs/README.md`](docs/README.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md)

## OneAquaHealth links

[Official page](https://www.oneaquahealth.eu/oneaquahealth-ieee-global-hackathon/) · [Factsheets](https://www.oneaquahealth.eu/app/uploads/2026/09/FactSheets_Combined_zenodo_f_citation_F_16092026.pdf) · [Field protocols](https://www.oneaquahealth.eu/app/uploads/2026/09/Field-Sampling-protocols-OAH_citation_Final_16092026.pdf) · [FHIR IG](https://github.com/hl7-eu/oah) · [CS app](https://apps.oneaquahealth.eu/login) · [Resilience Map](https://apps.oneaquahealth.eu/resmap/) · [GEOSSIP](https://apps.oneaquahealth.eu/eo)

## License

MIT. See [`LICENSE`](LICENSE).
