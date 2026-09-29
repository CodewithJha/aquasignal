# Configuration

All configuration comes from environment variables. The app does **not** load `.env` by itself. Load it in your shell with `set -a; source .env; set +a`, or pass it to Docker with `docker run --env-file .env`. Never commit real keys: `.env` is git-ignored and `.env.example` is the template.

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `<repo>/data/confirmgate.sqlite3` locally; `sqlite:////data/confirmgate.sqlite3` in Docker | SQLite file. Accepts `sqlite:///relative.db` (relative to the repo root), `sqlite:////absolute.db`, or a bare path. Parent directories are created and migrations run on start. A `postgres://` or `postgresql://` URL uses PostgreSQL instead (psycopg 3; migrations from `app/persistence/migrations/postgres/`). The URL is never logged. |
| `MAX_UPLOAD_BYTES` | `10485760` (10 MB) | Largest request body accepted. Larger requests (for example a big photo on `/upload`) get a plain HTTP 413 page. Only the photo's file name is recorded, so there is no reason to raise this much. Invalid or non-positive values fall back to the default. |
| `PORT` | `8000` | Used by the Docker `CMD`. Locally, pass it to uvicorn: `--port ${PORT:-8000}`. |
| `AI_PROVIDER` | `null` | `null` / `none` / `off`: no AI and no network. `fake`: deterministic offline stub for tests and demos. `openai` (aliases `http`, `provider`): any OpenAI-compatible `/chat/completions` endpoint. Unknown values fall back to `null`. |
| `AI_BASE_URL` | `https://api.openai.com/v1` | Base URL of the OpenAI-compatible endpoint, for example `https://api.featherless.ai/v1` or a local server. |
| `AI_MODEL` | `gpt-4o-mini` | Model id sent to the endpoint. Set it to a model your provider serves. |
| `AI_API_KEY` | unset | Bearer key. `OPENAI_API_KEY` is accepted as a fallback. If `AI_PROVIDER=openai` and no key is set, the app **falls back to `null`**. |
| `AI_TIMEOUT` | `8` | Seconds per AI request, clamped to 1–30. There are no retries. |
| `DEMO_MODE` | `false` | `true` / `1` / `yes` / `on` enables `python -m app.demo.reset` and a "Public demo — data may be reset" note. Anything else leaves the data alone. See the README section "Public demo behavior". |
| `DEMO_RESET_ON_START` | `false` | Restores the seeded demo dataset on app start. Ignored unless `DEMO_MODE` is also enabled. |

Example: optional AI through Featherless (OpenAI-compatible, no code changes; placeholder values):

```bash
AI_PROVIDER=openai
AI_BASE_URL=https://api.featherless.ai/v1
AI_MODEL=<model id served by Featherless>
AI_API_KEY=<your key — set in the host's secret store, never commit>
AI_TIMEOUT=8
```

Notes:

- If an AI endpoint hangs, a submission can take about 2× `AI_TIMEOUT` before the app continues without AI.
- The API key is never logged, never written to provenance, and never returned by `/healthz`.
- AI provenance records a provider label taken from the endpoint host. It is `openai` for `api.openai.com` and `openai-compatible:<host>` for anything else. It also records the model id and the prompt version.
- AI failures or timeouts never block the core flow. The UI shows "AI advisory unavailable" and continues.
- There is no auth configuration because there is no authentication. See [`../SECURITY.md`](../SECURITY.md).
- There is one uvicorn worker. SQLite runs in WAL mode with a 5 s busy timeout, which suits a single-instance demo. Do not scale out to multiple containers against the same file.
- On PostgreSQL, each unit of work takes a transaction-scoped advisory lock (the equivalent of SQLite's `BEGIN IMMEDIATE`), with a 5 s `lock_timeout`. Writes are serialized the same way as on SQLite.
- `TEST_DATABASE_URL` (tests only): run `pytest` against PostgreSQL instead of temp SQLite files.
