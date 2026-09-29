# ConfirmGate — AI Policy (Phase 8)

Status: ACTIVE (Phase 8)  
Date: 21 Sep 2026  
Authority: `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md`, `docs/REQUIREMENTS.md` AI-001–006, `docs/HITL-POLICY.md`

## 1. Human authority

**Human confirmation is authority.** AI suggestions are advisory only. Deterministic `FlagEngine` remains authoritative for quality rules. FHIR export happens only after `FINALIZED`.

| Actor | May |
|---|---|
| AI provider | Suggest bounded categorical values; optionally rephrase existing flag messages |
| Citizen / reviewer | Accept (“Use suggestion”) or decline (“Keep my value”); confirm; finalize |
| AI provider | **Must not** confirm, reject, finalize, export FHIR, write DB, or mutate domain fields directly |

Core product **must** work with `NullAiAssist` and **no API key**. If removing AI breaks the core flow, Phase 8 has failed.

## 2. Allowed capabilities (Phase 8)

1. **Constrained protocol-lite categorical suggestions** (foam / colour / smell / A-P-E vegetation bins, etc.) validated against internal domain vocabulary before UI.  
2. **Optional “explain this deterministic flag”** — plain-language restatement grounded in the existing flag `message`. Cannot change severity, code, rule_id, or blocking.

## 3. Prohibited outputs / behaviors

AI must **never**:

- Produce trust / confidence scores as authority  
- Decide valid / invalid  
- Infer ecological health, BMWP, IBD, EFI  
- Claim pathogen / disease / outbreak / AMR / pharma / lab results  
- Claim water safety or diagnosis  
- Auto reject / confirm / finalize  
- Generate FHIR or TemporaryOahSystem codes  
- Bypass FlagEngine  
- Alter workflow state  
- Write to the database or access DB repositories  
- Analyze photos (media bytes pipeline not ready — do not fake image analysis)

## 4. Provider architecture

| Provider | When | Network |
|---|---|---|
| `NullAiAssist` | Default (`AI_PROVIDER=null` / unset / invalid) | None |
| `FakeAiAssist` | `AI_PROVIDER=fake` or tests | None |
| `OptionalProviderAiAssist` | `AI_PROVIDER=openai` (or `http` / `provider`) **and** `AI_API_KEY` set | HTTP only when selected |

Composition selects via `app.ai.factory.build_ai_assist`. No network on pytest / startup by default.

## 5. Configuration

| Env | Default | Notes |
|---|---|---|
| `AI_PROVIDER` | `null` | `null` \| `fake` \| `openai` |
| `AI_MODEL` | `gpt-4o-mini` | Used by HTTP provider only |
| `AI_API_KEY` | unset | Never commit; `.env.example` placeholders only |
| `AI_TIMEOUT` | `8` | Bounded 1–30 seconds; minimal / no retries |
| `AI_BASE_URL` | OpenAI v1 | Optional |

Legacy `OPENAI_API_KEY` is accepted as a fallback alias for the key only.

## 6. Data sent / retained

**Sent to HTTP provider (when enabled):** empty-field codes + allowlisted vocabularies + current field values (protocol-lite only); or a single flag’s id/code/severity/message for explain. No API keys in prompts. No full PII dumps. Photo bytes are **not** sent in Phase 8.

**Retained locally:** non-authoritative `packet.suggestions` (structured field advisories + optional flag explanations); provenance records provider / model / prompt version / purpose / timestamp / packet / suggested field. **Never** store API keys or auth headers in provenance or logs.

**Transient preference:** suggestions live in the advisory map until human accept/decline; accepting copies into `fields` with `source=ai_suggestion_accepted` then re-runs FlagEngine.

## 7. Structured output contract

Typed `AiSuggestion`: `field`, `suggested_value`, `explanation`, `model`, `provider`, `model_version`, `prompt_version`, `purpose`.

Malformed / schema-fail / out-of-vocabulary / prohibited-token explanations are **rejected** before UI. Versioned prompts live in `app/ai/prompts.py` (`PROMPT_VERSION`, `FLAG_EXPLAIN_PROMPT_VERSION`) — not in routes, templates, or domain.

## 8. Failure behavior

Timeout, unavailable, HTTP error, rate limit, malformed, schema fail → continue manually with user-visible **“AI assistance unavailable”**; **never** fail submission. Bounded timeout; no retry storms.

## 9. Privacy

- Do not log `Authorization` headers or API keys  
- Do not put keys in provenance  
- Prefer opaque packet ids; no multi-user auth yet (see HITL-POLICY)  
- Reviewer desk may show the same advisory panel with the same AI vs flag vs human distinction  

## 10. Null fallback

Unset, empty, unknown, or HTTP-without-key configurations resolve to `NullAiAssist`. Demo and CI remain offline-safe.

## 11. Investigation Copilot (AquaSignal A6)

Optional **InvestigationCopilotPort** restates a frozen SYSTEM ANALYSIS brief for triage only.

| Provider | When |
|---|---|
| `NullInvestigationCopilot` | Default (`AI_PROVIDER=null` / unset / invalid) |
| `FakeInvestigationCopilot` | `AI_PROVIDER=fake` or tests |
| HTTP adapter | Same `AI_PROVIDER=openai` + key path as Phase 8 |

Rules:

- Copilot **must not** mutate `AnalysisRun`, signals, relations, cases, ConfirmGate packets, or FHIR  
- Invalid ids / forbidden vocab / malformed / timeout / unavailable → soft fail (`rejected` / `unavailable` / `timeout`); brief page still loads  
- Same env defaults as Phase 8; composition wires both ports from `AiSettings`  
- UI labels: **SYSTEM ANALYSIS** (authority for detectors) · **AI ADVISORY** (optional) · **HUMAN DECISION** (cases)

---

*Phase 8 + A6 AI policy. Phase 9 = security / EXIF / retention — not started.*
