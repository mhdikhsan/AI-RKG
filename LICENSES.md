# Licences

Imported entries carry `dct:license` and `dct:source`; output files are described in `build/dataset.ttl`.

| File | Content | Licence | Attribution |
|---|---|---|---|
| `build/imported_risks_ibm.nt` | 99 IBM AI Risk Atlas risks | Apache-2.0 | "IBM AI Risk Atlas, via IBM AI Atlas Nexus (Apache-2.0)" + notice below |
| `build/imported_risks_mit.nt` | 24 MIT AI Risk Repository subdomains | CC BY 4.0 | "MIT AI Risk Repository, Slattery et al. (CC BY 4.0)" |
| `build/imported_risks_owasp.nt` | 10 OWASP LLM Top 10 2025 entries (no OWASP text) | CC BY-SA 4.0 | "OWASP Top 10 for LLM Applications 2025, OWASP Foundation (CC BY-SA 4.0)" |
| `build/imported_crosswalks.nt` | 108 SKOS links from Nexus SSSOM sets | Apache-2.0 | `staging/crosswalks.csv` |
| `build/imported_mitigations.nt` | 831 MIT mitigation controls | CC BY 4.0 | "MIT AI Risk Mitigation Taxonomy, via IBM AI Atlas Nexus (CC BY 4.0)" |
| `build/manual_mitigation_links.nt` | curated control-to-risk links | CC BY 4.0 (assumed) | `staging/manual_mitigation_links.csv` |
| `build/accepted_mitigation_links.nt` | accepted LLM link candidates | CC BY 4.0 | `staging/accepted_mitigation_links.csv` |
| `build/accepted_motifs.nt` | accepted risk motifs from AIID and AVID | CC BY-SA 4.0 | "AI Incident Database (CC BY-SA 4.0); AI Vulnerability Database (MIT)" |
| `ontology/new_design/*.ttl`, code | authored | not decided | - |
| `build/airkg-core-kg.ttl` | merge of the above | mixed, strictest CC BY-SA 4.0 | all of the above |

AIID and AVID data are LLM input only and not in the graph.

## OWASP

If `copy_descriptions.owasp` is `true`, OWASP descriptions enter the OWASP file and the merged graph, and any release containing them must be CC BY-SA 4.0.

## Apache-2.0 notice

Contains data from IBM AI Atlas Nexus (https://github.com/IBM/ai-atlas-nexus), Copyright IBM Corporation, Apache License 2.0. Data were transformed from YAML/TSV to RDF.
