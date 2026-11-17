# AI-RKG core knowledge graph – statistics

Computed from sources fetched 2026-11-17, Nexus commit `54fcc4e935150004dfec483d32387a58225e09ba`.
Merged graph: `build/airkg-core-kg.ttl`, 10758 triples.

## Individuals per class (asserted `rdf:type`)

Authored = in `ak:` (core module); pipeline = minted from `base_iri` (imported or reused).

| Class | Authored | Pipeline | Total |
|---|---|---|---|
| `ak:Risk` | 5 | 133 | 138 |
| `ak:Consequence` | 5 | 0 | 5 |
| `ak:Mitigation` | 0 | 11 | 11 |
| `ak:TechnicalMitigation` | 3 | 102 | 105 |
| `ak:OrganisationalMitigation` | 3 | 718 | 721 |
| `ak:Role` | 0 | 0 | 0 |
| `ak:ComponentRole` | 29 | 5 | 34 |
| `ak:StakeholderRole` | 6 | 18 | 24 |
| `ak:Motif` | 14 | 0 | 14 |
| `ak:Condition` | 6 | 0 | 6 |
| `ak:RiskPattern` | 7 | 0 | 7 |
| `ak:MitigationPattern` | 7 | 0 | 7 |
| `ak:ContextElement` | 0 | 0 | 0 |
| `ak:AutonomyLevel` | 4 | 0 | 4 |
| `ak:DataType` | 2 | 0 | 2 |
| `ak:DeploymentEnvironment` | 3 | 0 | 3 |
| `ak:Domain` | 2 | 0 | 2 |
| `ak:Purpose` | 2 | 0 | 2 |
| `ak:Task` | 2 | 0 | 2 |

## Imported risks per catalogue

| Catalogue | Risks | With description | Excluded | Licence |
|---|---|---|---|---|
| IBM AI Risk Atlas | 99 | 99 | 0 | Apache-2.0 |
| MIT AI Risk Repository (Domain Taxonomy) | 24 | 24 | 9 | CC BY 4.0 |
| OWASP Top 10 for LLM Applications 2025 | 10 | 0 | 0 | CC BY-SA 4.0 |
| **Total** | 133 | 123 | 9 |  |

## Crosswalks between imported risks

| Predicate | Links |
|---|---|
| `skos:broadMatch` | 23 |
| `skos:exactMatch` | 1 |
| `skos:narrowMatch` | 7 |
| `skos:relatedMatch` | 77 |
| **Total** | 108 |

| Nexus mapping file | Rows | Kept | Dropped (reason: count) |
|---|---|---|---|
| ibm2ibm.tsv | 16 | 16 | — |
| ibm2owasp.tsv | 73 | 31 | duplicate row: 1, object sssom:NoTermFound: 15, predicate_modifier Not (negated mapping): 26 |
| mit-ai-risk-repository_ibm-risk-atlas.tsv | 252 | 61 | causal_facet: 189, duplicate row: 2 |

## Mitigations

| Type rule result (MIT top category) | Controls |
|---|---|
| `ak:Mitigation` | 11 |
| `ak:OrganisationalMitigation` | 718 |
| `ak:TechnicalMitigation` | 102 |
| **Total MIT controls** | 831 |

Candidate mitigation→risk links (LLM, `llm_mitigation/`):

- proposed: 0 (LLM run not done yet)
- accepted by review: 0
- `ak:mitigates` triples in the graph: 7 (7 authored, 0 from accepted candidates)

## Roles: grounded vs. proposed

Grounded = has `ak:source`, or `rdfs:seeAlso` / `skos:*Match` to an external IRI. Proposed = neither.

| Class | Origin | Roles | Grounded | Proposed |
|---|---|---|---|---|
| `ak:ComponentRole` | authored | 29 | 4 | 25 |
| `ak:ComponentRole` | reused | 5 | 5 | 0 |
| `ak:StakeholderRole` | authored | 6 | 0 | 6 |
| `ak:StakeholderRole` | reused | 18 | 18 | 0 |

Reused roles: BEAM (`role/beam/*`, via `rdfs:seeAlso` to BEAM classes); ISO/IEC 22989 (`role/iso22989/*`, names from a secondary source, see `LICENSES.md`).

## Validation

**PASS** — 0 errors, 5 warnings. (details: `build/reports/validation.md`).
