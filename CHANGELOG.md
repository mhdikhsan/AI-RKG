# Changelog

## 0.1.0 – 2026-11-17

First version of the construction pipeline for the core AI Risk Knowledge Graph.

- Fetches IBM AI Atlas Nexus at a pinned commit (plus DPV and BEAM) and records checksums in `sources/manifest.json`.
- Imports 133 catalogue risks (IBM AI Risk Atlas 99, MIT AI Risk Repository 24, OWASP Top 10 for LLM Applications 2025 10), 108 crosswalks between them and 831 MIT mitigation controls, via RML mappings (Morph-KGC).
- Reuses component roles from BEAM (5) and stakeholder role names from ISO/IEC 22989 (18); optional hand-written role grounding.
- Merges everything with the core module (unchanged) into `build/airkg-core-kg.ttl`; validates with HermiT (OWL consistency) and SHACL; checks that the AI system module still works.
- Reports: statistics, authored vs. imported risks, roles alignment, risk-pattern coverage. Static site with one page per entry.
- `llm_mitigation/`: LLM-assisted, human-reviewed mitigation→risk link candidates (not run yet).