# Roles alignment: authored (core module) vs. reused (BEAM, ISO/IEC 22989)

Computed from sources fetched 2026-11-17, Nexus commit `54fcc4e935150004dfec483d32387a58225e09ba`.

The core module is not changed. Correspondences below are *proposals* for your decision.

## BEAM process roles (component roles)

| Reused role | IRI | BEAM class | Target parent | Authored counterpart (via `rdfs:seeAlso`) | Authored parent | Status |
|---|---|---|---|---|---|---|
| Engineer step | `role/beam/engineer` | `beam:Engineer` | Generate step | `ak:EngineerStepRole` (Engineer step) | — (core level) | **conflict**: target specialises Generate step, authored is at core level |
| Generate step | `role/beam/generate` | `beam:Generate` | — | — | — | **missing** in authored list |
| Infer step | `role/beam/infer` | `beam:Infer` | — | `ak:InferStepRole` (Infer step) | — (core level) | corresponds |
| Train step | `role/beam/train` | `beam:Train` | Generate step | `ak:TrainStepRole` (Train step) | — (core level) | **conflict**: target specialises Generate step, authored is at core level |
| Transform step | `role/beam/transform` | `beam:Transform` | — | `ak:TransformStepRole` (Transform step) | — (core level) | corresponds |

BEAM's own class hierarchy (from `beam_core.ttl`):

- `beam:Engineer` rdfs:subClassOf `beam:Generate`
- `beam:Generate` rdfs:subClassOf `beam:Process`
- `beam:Infer` rdfs:subClassOf `beam:Process`
- `beam:Train` rdfs:subClassOf `beam:Generate`
- `beam:Transform` rdfs:subClassOf `beam:Process`

### Authored `ak:GenerationStepRole`

- name: "Generation step"; specialises: Infer step.
- Target (prompt): "Content generation step" under Infer step (BEAM *Infer*, not *Generate*). Parent already matches; name differs (rename needed in the core module).
- Risk of confusion: the reused `role/beam/generate` ("Generate step", BEAM *Generate* = producing a model) is a different role.

## ISO/IEC 22989 stakeholder roles

| Reused role | Clause | Parent | Authored counterpart (name match) |
|---|---|---|---|
| AI auditor (`role/iso22989/ai-auditor`) | 5.19 | ai-partner | **missing** in authored list |
| AI customer (`role/iso22989/ai-customer`) | 5.19 | — | `ak:AICustomer` |
| AI developer (`role/iso22989/ai-developer`) | 5.19 | ai-producer | **missing** in authored list |
| AI evaluator (`role/iso22989/ai-evaluator`) | 5.19 | ai-partner | **missing** in authored list |
| AI partner (`role/iso22989/ai-partner`) | 5.19 | — | `ak:AIPartner` |
| AI platform provider (`role/iso22989/ai-platform-provider`) | 5.19 | ai-provider | **missing** in authored list |
| AI producer (`role/iso22989/ai-producer`) | 5.19 | — | `ak:AIProducer` |
| AI provider (`role/iso22989/ai-provider`) | 5.19 | — | `ak:AIProvider` |
| AI service or product provider (`role/iso22989/ai-service-or-product-provider`) | 5.19 | ai-provider | **missing** in authored list |
| AI subject (`role/iso22989/ai-subject`) | 5.19 | — | `ak:AISubject` |
| AI system integrator (`role/iso22989/ai-system-integrator`) | 5.19 | ai-partner | **missing** in authored list |
| AI user (`role/iso22989/ai-user`) | 5.19 | ai-customer | **missing** in authored list |
| Data provider (`role/iso22989/data-provider`) | 5.19 | ai-partner | **missing** in authored list |
| Data subject (`role/iso22989/data-subject`) | 5.19 | ai-subject | **missing** in authored list |
| Other subjects (`role/iso22989/other-subjects`) | 5.19 | ai-subject | **missing** in authored list |
| Policy makers (`role/iso22989/policy-makers`) | 5.19 | relevant-authorities | **missing** in authored list |
| Regulators (`role/iso22989/regulators`) | 5.19 | relevant-authorities | **missing** in authored list |
| Relevant authorities (`role/iso22989/relevant-authorities`) | 5.19 | — | **missing** in authored list |

Authored stakeholder roles with no ISO counterpart by name: `ak:RelevantAuthority` (Relevant authority).

## Grounding of authored roles

A role is *grounded* if it has `ak:source` or `rdfs:seeAlso`/`skos:*Match` to an external IRI.

- Component roles: 4 of 29 grounded.
- Stakeholder roles: 0 of 6 grounded.

Authored component roles not grounded (proposed, local): `ak:ControlStepRole`, `ak:DerivedDataRole`, `ak:EmbeddingModelRole`, `ak:GeneratedOutputRole`, `ak:GenerationStepRole`, `ak:GenerativeModelRole`, `ak:HumanOperatorRole`, `ak:IndexingStepRole`, `ak:InputDataRole`, `ak:KnowledgeSourceRole`, `ak:OperatorRole`, `ak:OutputDataRole`, `ak:PredictiveModelRole`, `ak:PromptAssemblyStepRole`, `ak:PromptRole`, `ak:RedactionStepRole`, `ak:RepresentationModelRole`, `ak:RetrievalStepRole`, `ak:RetrievedContentRole`, `ak:ReviewerRole`, `ak:ScreeningStepRole`, `ak:SourceDataRole`, `ak:TrainingDataRole`, `ak:UserInputRole`, `ak:VectorIndexRole`.
