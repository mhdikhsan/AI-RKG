# Mapping checks

Computed from sources fetched 2026-11-17, Nexus commit `54fcc4e935150004dfec483d32387a58225e09ba`.

| Mapping | Triples |
|---|---|
| `risks.rml.ttl` | 1320 |
| `crosswalks.rml.ttl` | 108 |
| `mitigations.rml.ttl` | 8299 |

| Output file | Triples | Licence |
|---|---|---|
| `build/imported_crosswalks.nt` | 108 | https://www.apache.org/licenses/LICENSE-2.0 |
| `build/imported_mitigations.nt` | 8299 | https://creativecommons.org/licenses/by/4.0/ |
| `build/imported_risks_ibm.nt` | 990 | https://www.apache.org/licenses/LICENSE-2.0 |
| `build/imported_risks_mit.nt` | 240 | https://creativecommons.org/licenses/by/4.0/ |
| `build/imported_risks_owasp.nt` | 90 | https://creativecommons.org/licenses/by-sa/4.0/ |

Imported risks per catalogue: {'ibm': 99, 'mit': 24, 'owasp': 10}; mitigations: 831.

## Checks

- subject IRIs follow `{base_iri}risk/{nexus_id}` / `{base_iri}mitigation/{nexus_id}`
- no literal-valued `skos:*Match`
- crosswalk triples = staged rows; typed risks = staged rows

Result: **PASS**
