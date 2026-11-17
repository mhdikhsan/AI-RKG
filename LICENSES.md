# Licences and attribution

Licences checked against the sources at Nexus commit `54fcc4e935150004dfec483d32387a58225e09ba`. Each imported entry also carries `dct:license` and `dct:source`; each output file is described in `build/dataset.ttl`.

| File | Content | Licence | Attribution |
|---|---|---|---|
| `build/imported_risks_ibm.nt` | 99 IBM AI Risk Atlas risks incl. descriptions | Apache-2.0 | "IBM AI Risk Atlas, via IBM AI Atlas Nexus (Apache-2.0)." Apache-2.0 notice: see below. |
| `build/imported_risks_mit.nt` | 24 MIT AI Risk Repository domain-taxonomy subdomains incl. descriptions | CC BY 4.0 | "MIT AI Risk Repository, Slattery et al. (CC BY 4.0)." https://airisk.mit.edu/ |
| `build/imported_risks_owasp.nt` | 10 OWASP Top 10 for LLM Applications 2025 entries: name, identifier, URL, links — **no OWASP text** (`copy_descriptions.owasp: false`) | CC BY-SA 4.0 | "OWASP Top 10 for LLM Applications 2025, OWASP Foundation (CC BY-SA 4.0)." |
| `build/imported_crosswalks.nt` | 108 SKOS links from Nexus SSSOM mapping sets | Apache-2.0 (stated in the TSV headers) | Mapping provenance per row in `staging/crosswalks.csv` |
| `build/imported_mitigations.nt` | 831 MIT mitigation controls incl. descriptions | CC BY 4.0 | "MIT AI Risk Repository mitigation database / Draft AI Risk Mitigation Taxonomy, via IBM AI Atlas Nexus (CC BY 4.0)." |
| `build/reused_roles_beam.nt` | 5 roles referring to BEAM process classes (IRIs only) | — (only IRIs; BEAM file not redistributed, its licence is not stated) | BEAM core, https://semsys.ai.wu.ac.at/beam/ |
| `build/reused_roles_iso22989.nt` | 18 stakeholder role *names* and hierarchy of ISO/IEC 22989:2022 clause 5.19 (no standard text), taken from a secondary summary (ai42001.ai) | — (names only) | ISO/IEC 22989:2022 |
| `build/accepted_mitigation_links.nt` | human-accepted LLM candidate links (when present) | follows the MIT mitigations (CC BY 4.0) | `staging/accepted_mitigation_links.csv` (model, prompt hash, date, reviewer) |
| `ontology/*.ttl`, pipeline code | authored | to be decided by the authors | — |
| `build/airkg-core-kg.ttl` | merge of all of the above | mixed: the most restrictive part is CC BY-SA 4.0 (OWASP); see below | all of the above |

## OWASP and share-alike

By default no OWASP text is copied. The OWASP-derived triples (`imported_risks_owasp.nt`) are names, codes, URLs and links. If `copy_descriptions.owasp` is set to `true`, the OWASP descriptions enter only `build/imported_risks_owasp.nt` and the merged graph; that file — and any release containing it — must then be distributed under **CC BY-SA 4.0** and the release notes must say so.

## Apache-2.0 notice (IBM AI Atlas Nexus content and mappings)

Contains data from IBM AI Atlas Nexus (https://github.com/IBM/ai-atlas-nexus), Copyright IBM Corporation, licensed under the Apache License, Version 2.0 (https://www.apache.org/licenses/LICENSE-2.0). The data were transformed (YAML/TSV → RDF); see `scripts/stage.py` and `mappings/`.

## Things found in the sources that need a check

- MIT controls quote texts from many third-party documents (NIST AI 600-1, UK Government, FLI, papers). The MIT database is CC BY 4.0; the licences of the quoted originals are not stated in Nexus.
- The AIUC-1 framework (not imported) states no licence in Nexus.
- BEAM core (`beam_core.ttl`) states no licence; it is used only to check IRIs and is not redistributed (git-ignored).
- The ISO/IEC 22989 role names come from a secondary source and are not verified against the standard.
