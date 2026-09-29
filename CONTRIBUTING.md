# Contributing

This repository is a hackathon submission for OneAquaHealth Track 3. Read [`AGENTS.md`](AGENTS.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) before changing scope.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                       # full suite, no network, no API keys
ruff check .                 # lint (pip install ruff==0.13.3)
uvicorn app.main:app --reload --port 8000
```

Dependencies: top-level runtime packages go in `requirements.in`. The fully pinned closure in `requirements.txt` is what Docker and CI install. After changing `requirements.in`, regenerate with `uv pip compile requirements.in -o requirements.txt` or pip-tools. Test-only tools go in `requirements-dev.txt`.

## Conventions

- Keep layering intact (see the module map). Architecture tests will fail if `app/domain`, `app/flags`, or `app/signals` import web, persistence, AI, or FHIR code.
- Routes stay thin and synchronous (`def`, not `async def`). Business rules belong in `app/application` or lower layers.
- No composite trust scores, no image analysis, and no pollution, pathogen, disease, or water-safety claims, in code or in UI copy.
- AI is advisory. It must never confirm, finalize, change signals, or decide cases, and the app must run fully with `AI_PROVIDER=null`.
- FHIR is exported only for `FINALIZED` packets, with `Observation.status = final`. Prefer refusal over an invalid Bundle.
- Tests use a temporary SQLite path (`tmp_path`) and never the shared `data/` database.
- Match the surrounding code style. Do not mass-reformat.

**Phase naming.** Test and document names carry the phase that introduced them: `phase1`–`phase8` for ConfirmGate, `a1`–`a6` for AquaSignal, and `p0`–`p2` for the integration, hardening, and deployment passes. These are history markers only and do not mean anything at runtime.

## Adding a detector

1. Implement the `SignalDetector` protocol (`app/signals/protocol.py`) in `app/signals/detectors/`. It must be pure: no I/O and no randomness. Give it its own `DETECTOR_VERSION`.
2. Add a frozen params dataclass with deterministic `to_dict` in `app/signals/params.py`, and wire default params in `app/application/analysis_policy.py`.
3. Register it in the fixed order in `app/signals/registry.py` and **bump `DETECTOR_SET_VERSION`**.
4. Add tests under `tests/signals/` covering determinism, insufficient evidence, and edge cases. Update [`docs/SIGNAL-ENGINE.md`](docs/SIGNAL-ENGINE.md).
5. Detector output describes evidence patterns (change, conflict, insufficiency), never environmental or health conclusions.

If you change the synonym table in `app/signals/vocabulary.py`, bump `VOCABULARY_CANONICALIZATION_VERSION`. It is part of the snapshot hash.

## Adding an AI provider

1. Implement `AiAssistPort` (`app/ai/port.py`) and/or `InvestigationCopilotPort` (`app/ai/investigation_port.py`). For OpenAI-compatible endpoints, reuse `app/ai/http_chat.py`. Usually you only need to set `AI_BASE_URL`, with no new code.
2. Validate every output through `app/ai/validate.py` / `app/ai/investigation_validate.py`, and route free text through `app/ai/claim_safety.py`.
3. Select it in `app/ai/factory.py` from `AiSettings`. Missing configuration must fall back to Null.
4. Tests must mock HTTP (see `tests/ai/test_p1_investigation_provider_http.py`). CI has no keys and no network.

## Adding a FHIR mapping

1. Verify the code, profile, and cardinality against the [OAH IG](https://github.com/hl7-eu/oah) first, and record the evidence in [`docs/FHIR-SPEC.md`](docs/FHIR-SPEC.md). Never invent codes or systems.
2. Add the coding to `app/fhir/registry.py`. Mapper and guard changes go in `app/fhir/mapper.py` and `app/fhir/guard.py`.
3. Add tests to `tests/test_fhir_phase5.py`. Unverified values must be refused (`UnsupportedOahMapping`).

## Pull requests

Keep them small. The full test suite and ruff must pass. Describe any behavior change in user-visible terms.
