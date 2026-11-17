# Authored example risks vs. imported catalogue risks

Computed from sources fetched 2026-11-17, Nexus commit `54fcc4e935150004dfec483d32387a58225e09ba`.

Authored risks are the `ak:Risk` individuals in `ontology/airkg-core.ttl`; imported risks are in `build/imported_risks_*.nt`. Nothing is merged or rewritten.

| Authored risk | `ak:identifier` | Name | `ak:source` | Matching imported risk | Matched by | Other exact/close matches of the imported risk | Used by (risk patterns / mitigation patterns / mitigations / consequences) |
|---|---|---|---|---|---|---|---|
| `ak:Misinformation` | LLM09:2025 | Misinformation | https://genai.owasp.org/llm-top-10/ | `risk/llm092025-misinformation` (LLM09:2025 Misinformation) | identifier = catalogue code | — | 1 / 1 / 1 / 1 |
| `ak:NonDisclosure` | atlas-non-disclosure | Non-disclosure | https://arxiv.org/abs/2503.05780 | `risk/atlas-non-disclosure` (Non-disclosure) | identifier = Nexus id | — | 1 / 1 / 1 / 1 |
| `ak:PromptInjection` | LLM01:2025 | Prompt injection | https://genai.owasp.org/llm-top-10/ | `risk/llm01-prompt-injection` (LLM01:2025 Prompt Injection) | identifier = catalogue code | skos:exactMatch `atlas-prompt-injection` | 2 / 2 / 2 / 2 |
| `ak:SensitiveInformationDisclosure` | LLM02:2025 | Sensitive information disclosure | https://genai.owasp.org/llm-top-10/ | `risk/llm022025-sensitive-information-disclosure` (LLM02:2025 Sensitive Information Disclosure) | identifier = catalogue code | — | 2 / 2 / 2 / 1 |
| `ak:SupplyChain` | LLM03:2025 | Supply chain | https://genai.owasp.org/llm-top-10/ | `risk/llm032025-supply-chain` (LLM03:2025 Supply Chain) | identifier = catalogue code | — | 1 / 1 / 1 / 1 |

5 of 5 authored risks have an imported counterpart.

## Observations

- Authored OWASP risks cite `https://genai.owasp.org/llm-top-10/` as `ak:source`; the imported ones cite the per-entry page.
- Authored risks carry the hand-written structure (consequences, risk patterns, mitigation patterns, mitigations); imported risks carry catalogue metadata and crosswalks. The two sets are not linked in RDF.
- Options (not applied): (a) keep both and link authored → imported with `skos:exactMatch`; (b) re-point the authored patterns/consequences/mitigations to the imported IRIs and drop the authored risks (requires editing the core module); (c) keep as is (two separate example sets).
