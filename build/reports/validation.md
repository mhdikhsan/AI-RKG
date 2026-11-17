# Validation report

Computed from sources fetched 2026-11-17, Nexus commit `54fcc4e935150004dfec483d32387a58225e09ba`.
## Summary

**PASS** — 0 errors, 5 warnings.


## 1. Parse

PASS: `build/airkg-core-kg.ttl` parses, 10758 triples.

## 2. OWL consistency (HermiT, bundled with owlready2 0.51)

PASS: consistent=True, unsatisfiable classes=none (HermiT: http://www.w3.org/2002/07/owl#Thing is satisfiable.; 1087 named individuals).
Self-test (planted contradiction: a second `ak:level` on an `ak:AutonomyLevel`): detected - check is effective.

## 3. SHACL (`shapes/core.shacl.ttl`)

PASS: 0 violations, 985 warnings.

| Severity | Message | Count |
|---|---|---|
| Warning | ak:Risk without ak:description | 10 |
| Warning | ak:Risk without ak:hasConsequence | 133 |
| Warning | mitigation not linked to any risk (ak:mitigates) | 831 |
| Warning | mitigation without ak:description | 11 |

133 of 138 risks have no `ak:hasConsequence` (all imported risks; the 5 authored risks have consequences). Reported as warning.

## 4. Competency queries (`queries/*.rq`)

Not run: no `queries/*.rq` yet (you will provide Q7, Q16, Q17 and `queries/expected.json`).

## 5. Dangling IRIs

PASS: 0 object IRIs in `http://example.org/airkg#` or `http://example.org/airkg/` that are never a subject.

## DPV IRIs used (existence check)

7 of 7 DPV IRIs found in DPV 2.3.

## 6. AI system module on top of the merged core

Parse: PASS (`ontology/airkg-system.ttl`; its `owl:imports <http://example.org/airkg/core>` is satisfied by loading the core graph directly).
Consistency (system + merged core): PASS (HermiT: http://www.w3.org/2002/07/owl#Thing is satisfiable.; 1120 named individuals).

| Baseline query | Rows before (original core) | Rows after (merged core) | Same rows |
|---|---|---|---|
| `system/component_roles.rq` | 14 | 14 | yes |
| `system/consequences_by_stakeholder.rq` | 10 | 10 | yes |
| `system/workflow_mitigations.rq` | 2 | 2 | yes |
| `system/workflow_motif_roles.rq` | 42 | 42 | yes |
| `system/workflow_risks.rq` | 4 | 4 | yes |

## Errors

none

## Warnings

- SHACL Warning: ak:Risk without ak:description (10)
- SHACL Warning: ak:Risk without ak:hasConsequence (133)
- SHACL Warning: mitigation not linked to any risk (ak:mitigates) (831)
- SHACL Warning: mitigation without ak:description (11)
- competency queries Q7/Q16/Q17 not provided yet (queries/*.rq, queries/expected.json)
