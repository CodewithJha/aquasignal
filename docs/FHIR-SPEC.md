# ConfirmGate — FHIR mapping specification (Phase 5)

**Status:** Phase 5 research gate + verified mapping contract  
**Checked:** 2026-09-21 (IST); HL7 validator run 2026-09-29 (§9.1)  
**Do not invent** OAH profiles, codes, slices, cardinalities, extensions, identifier systems, or value sets. Unverified → `[VERIFY]` / refuse.

---

## 1. Official source / version / date

| Item | Value |
|---|---|
| Source (CI build) | https://build.fhir.org/ig/hl7-eu/oah/ |
| Source (FSH) | https://github.com/hl7-eu/oah (`master`, cloned 2026-09-21) |
| Package | `hl7.eu.fhir.oah#0.1.0-ci-build` |
| IG version | `0.1.0-ci-build` (draft / continuous build) |
| FHIR version | R4 `4.0.1` |
| Canonical base | `http://hl7.eu/fhir/ig/oah` |
| Profile pages dated | LocationOah draft as of **2026-06-03**; ObservationIndicatorsOah draft as of **2026-06-11** |
| CodeSystem page | Temporary OAH Code System (experimental), CI build |

This is **not** a published ballot/release package. As of 2026-09-29 no built package is downloadable (CI build URL 404; not on packages.fhir.org); release validation compiles the FSH instead — see §9.1 for the validator run and exact results.

---

## 2. Profiles verified (canonical URLs)

| Computable name | Canonical URL | Used in Phase 5? |
|---|---|---|
| `LocationOah` | `http://hl7.eu/fhir/ig/oah/StructureDefinition/location-oah` | **Yes** |
| `ObservationIndicatorsOah` | `http://hl7.eu/fhir/ig/oah/StructureDefinition/observation-indicators-oah` | **Yes** (simple indicators) |
| `ObservationWithCompOah` | `http://hl7.eu/fhir/ig/oah/StructureDefinition/observation-with-component-oah` | **Deferred** — needs typed component slices (liveworts / trees / …); protocol-lite has aggregate A/P/E only |
| `SpecimenOah` | `http://hl7.eu/fhir/ig/oah/StructureDefinition/specimen-oah` | **No** — not invented; optional on Observations (`0..1`) |
| `ObservationHealthMeasureOah` | (health-measure profile) | **No** — out of protocol-lite scope |
| OAH `Provenance` profile | — | **None found** in IG FSH / artifacts |
| OAH `Bundle` profile | — | **None found** — use base R4 `Bundle.type = collection` |

### LocationOah — verified cardinality (FSH + CI)

| Element | Card. / constraint |
|---|---|
| `identifier` | **1..\*** |
| `name` | **1..1** |
| `mode` | **1..1**, pattern **`instance`** |
| `position` | **0..1** (comment: not all sites have GPS) |
| `position.longitude` / `latitude` | **1..1 when position present** |

**GPS rule:** emit `position` only when both `SiteRef.lat` and `SiteRef.lon` are present. Never invent coordinates.

### ObservationIndicatorsOah — verified constraints (FSH + CI)

| Element | Card. / constraint |
|---|---|
| `status` | **1..1**, required pattern **`final`** — never `preliminary` |
| `code` | **1..1**, binding preferred `OahIndicatorsNoHealthOahVs` |
| `subject` | **1..1**, `Reference(LocationOah)` |
| `effective[x]` | **1..1** |
| `performer` | **1..\*** |
| `value[x]` | **0..1**, `CodeableConcept` or `Quantity` |
| `specimen` | **0..1** → SpecimenOah (we omit) |

IG examples populate `performer` with **display-only** references (e.g. `performer.display = "OneAquaHealth Crete Lab"`). ConfirmGate follows that pattern using citizen/submitter display — not an invented Practitioner profile.

### ObservationWithCompOah — verified but deferred

- Parent of ObservationIndicatorsOah; `value[x] 0..0`; `component 1..\*` with slices `macrophytes`, `nonNativeMacrophytes`, `riparianVegetation`.
- Component codes require **typed** TemporaryOahSystem concepts (`liveworts`, `trees`, `*-non-native`, …).
- Protocol-lite stores aggregate `macrophytes` A/P/E and `riparian_vegetation` cover bins **without** type — mapping into WithComp slices would fabricate type codes → **refused / deferred**.

---

## 3. Terminology verified

| Artifact | Canonical URL / Id | Notes |
|---|---|---|
| CodeSystem `TemporaryOahSystem` | `http://hl7.eu/fhir/ig/oah/CodeSystem/temporarySystem-oah-eu` | `^experimental = true`, case-sensitive |
| VS Macrophytes values | `…/ValueSet/macrophytes-indicator-value-oah-vs` | `#absent`, `#present`, `#extensive` |
| VS Macrophytes type codes | `…/ValueSet/macrophytes-indicator-code-oah-vs` | typed plant forms — for WithComp |
| VS Non-native type codes | `…/ValueSet/nonnative-macrophytes-indicator-code-oah-vs` | WithComp only |
| VS Riparian codes | `…/ValueSet/riparian-vegetation-code-oah-vs` | `#riparianVegetation`, `#trees`, … |
| VS Riparian values | `…/ValueSet/riparian-vegetation-value-oah-vs` | `#0-20-percent` … `#81-100-percent` |
| VS Observation type w/ components | `…/ValueSet/observation-type-with-component-oah-vs` | `#macrophytes`, `#riparianVegetation`, `#nutrients` |
| VS OAH Indicators (non-health) | `…/ValueSet/oah-indicators-no-health-oah-vs` | preferred binding for Observation.code |

### Codes used in Phase 5 (must exist in TemporaryOahSystem)

| Code | Display (IG) |
|---|---|
| `foam` | Foam/colour/smell |
| `macrophytes` | Macrophytes |
| `riparianVegetation` | Riparian vegetation |
| `morophology` | Morphology of the streams (**exact CodeSystem spelling**; ConceptMap comment says `morphology` — we follow CodeSystem) |
| `absent` / `present` / `extensive` | A/P/E values |
| `0-20-percent` … `81-100-percent` | Riparian cover bins |

### Location identifier system (from IG examples, not invented)

IG Location examples use:

`identifier.system = "https://oneaquahealth.eu/location-id"`

ConfirmGate Location resources use that **verified** system. Identifier **value** comes from `SiteRef.fhir_location_identifier` (value portion if `system|value` pipe form).

---

## 4. Mapping table

Export authority = **confirmation snapshot** fields on a **FINALIZED** packet (not mutable draft).

| Internal key | FHIR resource / profile | Element | OAH code / system | Card. | Source |
|---|---|---|---|---|---|
| `SiteRef` | `Location` / LocationOah | `meta.profile` | profile URL above | 0..* | constant |
| `SiteRef.fhir_location_identifier` | Location | `identifier[0]` | system=`https://oneaquahealth.eu/location-id`; value=site id | 1..* | snapshot site |
| `SiteRef.display_name` | Location | `name` | — | 1..1 | site |
| — | Location | `mode` | `instance` | 1..1 | IG pattern |
| `SiteRef.lat/lon` | Location | `position` | — | 0..1 | only if both set |
| `foam` | Observation / ObservationIndicatorsOah | `code` | TemporaryOahSystem `#foam` | 1..1 | snapshot |
| `foam` value A/P/E | Observation | `valueCodeableConcept` | `#absent`/`#present`/`#extensive` | 0..1 | snapshot (see value map) |
| `colour`, `smell` | Observation (foam) | `note.text` | **not coded** | 0..1 | annotation only — no TemporaryOahSystem codes for colour/smell alone |
| `macrophytes` | Observation / ObservationIndicatorsOah | `code` + `valueCodeableConcept` | `#macrophytes` + A/P/E | 0..1 obs | snapshot |
| `riparian_vegetation` | Observation / ObservationIndicatorsOah | `code` + `valueCodeableConcept` | `#riparianVegetation` + percent codes | 0..1 obs | snapshot **only if value is OAH percent code** |
| `hydromorphology` | Observation / ObservationIndicatorsOah | `code` + `valueCodeableConcept` | `#morophology` + A/P/E | 0..1 obs | snapshot |
| packet `effective_at` | Observation | `effectiveDateTime` | ISO-8601 | 1..1 | packet |
| confirm actor / submitter | Observation | `performer[0].display` | — | 1..\* | confirmation / submitter_display |
| Location entry | Observation | `subject.reference` | Location entry `fullUrl` (`urn:uuid:…`) | 1..1 | bundle-local |
| — | Bundle | `type` | `collection` | 1..1 | FHIR-009 |
| — | Bundle | `id` | packet fhir_bundle_id / packet_id | 1..1 | packet |

### Internal value → TemporaryOahSystem value codes

| Internal (domain) | OAH code | Notes |
|---|---|---|
| `a` / `absent` / `none` (foam) | `absent` | verified CS codes |
| `p` / `present` | `present` | |
| `e` / `extensive` / `abundant` (foam) | `extensive` | `abundant`→`extensive` is ConfirmGate normalization of domain vocab onto verified A/P/E codes |
| riparian `0-20-percent` … `81-100-percent` | same | pass-through verified VS codes |
| riparian domain bins `0-25`, `25-50`, … | — | **Unsupported** — bins ≠ OAH VS → refuse field |

---

## 5. Unsupported / deferred mappings

| Item | Reason |
|---|---|
| `colour` / `smell` as separate Observations | No TemporaryOahSystem codes; ConceptMap maps Foam/colour/smell → single `#foam` |
| `macrophytes_non_native`, `riparian_non_native` | WithComp non-native slice needs typed `*-non-native` codes; protocol-lite is bool-ish only |
| `ObservationWithCompOah` typed components | No per-type citizen fields in Phase 5 scope |
| Specimen / Patient / HealthMeasure / Device | Out of scope; do not invent |
| FHIR `Provenance` resource | **No OAH Provenance profile**; IG does not require it. ConfirmGate uses **internal append-only audit** with `bundle_hash` + `mapper_version`. Base R4 Provenance deferred until IG requires or product mandate revises FHIR-007 |
| Domain riparian bins (`none`, `0-25`, …) | Not equal to OAH percent VS → `UnsupportedOahMapping` if present in snapshot |
| Fake / unknown internal codes | Guard / mapper refuse |
| GPS when lat/lon missing | Omit `position` (allowed 0..1) |

---

## 6. StructuralGuard requirements

Refuse export (prefer refusal over fabricate) unless **all** hold:

1. Packet exists / is the argument  
2. `workflow_state == FINALIZED` (not merely `CONFIRMED`)  
3. Site present with `fhir_location_identifier`  
4. Confirmation snapshot present  
5. Snapshot hash matches current fields  
6. No standing soft_block / hard_reject  
7. Not withdrawn/rejected (implied by FINALIZED)  
8. `effective_at` present (Observation `effective[x]` 1..1)  
9. Performer display resolvable (submitter_display or confirmation.confirmed_by)  
10. Snapshot field codes ⊆ supported export registry **or** explicitly annotated (colour/smell)  
11. No unsupported coded field values (e.g. unmapped riparian bins, non-native bools)  
12. `OAH_FHIR_MAPPER_VERSION` and `FLAG_RULES_VERSION` (rule engine) known constants  

---

## 7. Deterministic Bundle + hash

- Resource `id`s derived from `packet_id` + stable suffixes (`loc`, `obs-foam`, …) — no random UUIDs.  
- Entry `fullUrl` = `urn:uuid:` + RFC 4122 UUIDv5 of the resource id under a fixed namespace (deterministic). Observation `subject.reference` points at the Location entry's `fullUrl` (not a `#contained` reference).  
- Bundle `entry` order: Location, then Observations sorted by Observation.code coding.code.  
- Canonical JSON: UTF-8, `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.  
- `bundle_hash` = `sha256(canonical_bytes).hexdigest()` recorded on internal provenance (`fhir.export_digest` / finalize after extras).  
- Same FINALIZED packet + same `OAH_FHIR_MAPPER_VERSION` → same structure and hash.

---

## 8. Mapper version

```text
OAH_FHIR_MAPPER_VERSION = "0.1.1"
```

`0.1.1`: entry `fullUrl`s became valid `urn:uuid` UUIDs and Observation `subject` now resolves to the Location entry (was `#loc-…`). Bundles exported under `0.1.0` hash differently.

Recorded in export provenance (HITL Q7) alongside `rule_engine_version` / `FLAG_RULES_VERSION`.

---

## 9. Validator status

| Port | Status |
|---|---|
| `FhirValidatorPort` (runtime) | Optional adapter; default `NullFhirValidator` (no-op). The running app does **not** call an IG validator. |
| Release-time HL7 validation | Manual: [`scripts/validate_fhir.sh`](../scripts/validate_fhir.sh). Not part of pytest/CI (needs network, Node, Java or Docker). |
| StructuralGuard + golden shape tests | Every test run (`tests/test_fhir_phase5.py`) |

### 9.1 Release validation — 2026-09-29 (IST)

| Item | Value |
|---|---|
| Validator | Official HL7 FHIR Validator `validator_cli.jar` **6.10.4** (Git# 1b90fb13f77b, built 2026-09-04), run on Java 21 (`eclipse-temurin:21-jre` Docker) |
| FHIR version | `-version 4.0.1` |
| OAH IG | `hl7.eu.fhir.oah` `0.1.0-ci-build`, compiled from FSH at [`hl7-eu/oah@b907cf0`](https://github.com/hl7-eu/oah/commit/b907cf0869b59d82d9138b3d147fca66f333d911) (2026-06-11, latest `master`) with SUSHI 3.20.1 (0 errors, 0 warnings; 504 resources) |
| IG dependency | `hl7.fhir.uv.xver-r5.r4#0.1.0` (from the IG's `sushi-config.yaml`) |
| Terminology | `tx.fhir.org` |
| Inputs | Two Bundles from the real HTTP flow (upload → confirm → finalize → `GET /fhir/bundle`), fresh SQLite, `AI_PROVIDER=null`, mapper `0.1.1`: Coimbra (foam present, macrophytes p, riparian 41–60 %, hydromorphology a, colour brown, smell earthy) and Ghent (foam abundant, macrophytes e, riparian 81–100 %, hydromorphology e, colour grey, smell sewage). Each = 1 `Location` + 4 `Observation`. |

Why FSH compile instead of a package: no built OAH package is published — `https://build.fhir.org/ig/hl7-eu/oah/package.tgz` returns 404, the IG is absent from the build.fhir.org QA index, and `packages.fhir.org` reports `hl7.eu.fhir.oah` not found.

Command (as run by `scripts/validate_fhir.sh`):

```bash
java -jar validator_cli.jar bundle.json bundle2.json -version 4.0.1 \
  -ig oah-ig/fsh-generated/resources -ig hl7.fhir.uv.xver-r5.r4#0.1.0 \
  -output out.json
```

**Result (each Bundle): 0 errors, 5 warnings, 1 information.**

| Severity | Issue | Classification |
|---|---|---|
| warning ×5 | `dom-6`: resource should have narrative (`text`) — one per `Location` / `Observation` | Best-practice only; the OAH profiles do not require narrative. Not fixed. |
| information ×1 | `Bundle.meta.tag[0].system` `https://confirmgate.local/fhir/mapper` has no CodeSystem definition | Expected: private tag recording mapper version; tags are unconstrained. |

Negative control (same Bundle with `Location.mode=kind`, one Observation `status=preliminary` and no `performer`, one unknown value code) produced **8 errors** citing `location-oah` / `observation-indicators-oah` fixed values, `performer` min 1, the unknown TemporaryOahSystem code, and subject not matching `LocationOah`. So the OAH profiles and CodeSystem were actually enforced in the passing run.

Limitations: the IG is a draft continuous build with no published package; results are pinned to commit `b907cf0` and may change if the IG changes. `ObservationWithCompOah`, Specimen and Provenance are not emitted (§5), so they were not exercised.

Separate error types: `FhirExportRefused`, `StructuralGuardFailure`, `UnsupportedOahMapping`, `MissingRequiredOahData`, `FhirValidationFailure`, `FhirValidatorUnavailable`.

---

## 10. `[VERIFY]` open items

1. Whether foam/colour/smell should ever split into multiple Observations if TemporaryOahSystem gains colour/smell codes.  
2. ConceptMap `morphology` vs CodeSystem `morophology` typo — we follow CodeSystem.  
3. Whether display-only `performer` remains acceptable when IG tightens Practitioner bindings (currently commented out in FSH).  
4. Whether base R4 Provenance should be re-added despite no OAH profile (Requirements FHIR-007 vs Phase 5 “IG must require”).  
5. Official Location identifier system permanence (`https://oneaquahealth.eu/location-id` from examples).  
6. Riparian domain bin ↔ OAH percent equivalence (intentionally not mapped).  
7. `abundant`→`extensive` normalization for foam.  

---

## 11. Honesty language

ConfirmGate produces Bundles aligned to LocationOah / ObservationIndicatorsOah and the TemporaryOahSystem codes listed above. Say: “Validated with the HL7 FHIR Validator 6.10.4 against the `hl7-eu/oah` CI-build IG (FSH compiled at commit `b907cf0`): 0 errors, 5 best-practice warnings per Bundle (§9.1).” Do **not** say it conforms to a published OAH package (none exists), and do not imply the running app validates each export (runtime uses `NullFhirValidator`).
