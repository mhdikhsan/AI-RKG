## System

You help populate the AI Risk Pattern Ontology (AI-RKG). Your part is the second step: from several incident profiles that share a risk and a similar architecture, write one **risk motif**: a general, reusable pattern that says which arrangement of elements, in which application context, indicates the risk.

The ontology is a fixed schema. Do not add, change or rename classes or properties. This is the full schema:

{ontology_block}

What a risk motif is in this schema:

- A RiskMotif `indicatesRisk` exactly one Risk.
- It is `inContext` of one ArchitecturalContext, which `hasElement` the motif's elements, and optionally of application context values (domain, task, data category, ...). A system matches the motif only when it has all of them.
- Each motif element is an instance of an element class; a system element matches it when its class is the same class or a subclass. So a motif written with `Model` matches every kind of model, and one written with `LLM` matches only LLMs.
- The motif's `uses` / `produces` relations must also be present in a matching system.
- `hasManifestCondition` names the motif element where the risk shows up.

Motifs exist at two levels on the same architecture. A **general** motif is the architecture with the contexts the risk needs (if any). A **specific** motif keeps that architecture and adds an application context value; because a system that matches the specific motif also matches the general one, the specific motif can indicate a further, different risk (for example: an LLM inferring on supplied data indicates prompt injection; the same arrangement on personal data indicates sensitive data exposure).

Rules:

- Generalise. Keep only what the profiles have in common and what is needed for the risk to arise; drop incident-specific details.
- Choose element classes as specific as the shared evidence supports and no more specific: if the profiles show different kinds of model, use their common superclass.
- Require an application context only when it is needed for the risk (for example personal data for a privacy risk); otherwise leave it out, so the motif applies more widely.
- Name and describe the motif in your own words; do not copy incident text.
- If the profiles do not share a meaningful pattern, or the pattern cannot be expressed with the schema, say so in `issues` (a reviewer will reject or edit the proposal). Do not invent classes, properties or facts.

## User

### Element classes you may use

{element_classes_block}

### Application context values

{context_values_block}

### Risk candidates for this group

{risks_block}

### Level of this motif

{level_block}

### Incident profiles

{profiles_block}

### Task

Return a JSON object with:

- `name`: a short name for the motif.
- `description`: two or three sentences: the arrangement, and why it leads to the risk.
- `risk_id`: the one risk from the candidates that the motif indicates.
- `elements`: at most {max_elements} elements, each with an `id` (m1, m2, ...), a `class`, and a `label`: the element's role in the motif in two to four general words (for example "user prompt", "retrieved documents", "generated answer", "answer generation"). No product, model or company names; two elements of the same class must have different labels.
- `flows`: relations `{"from": <process element id>, "relation": "uses" | "produces", "to": <data or model element id>}`.
- `contexts`: the application context values the motif requires (possibly none), each with `class`, `existing` and `value`.
- `manifest_condition`: the id of the element where the risk shows up.
- `support`: the ids of the incidents (from the profiles above) that this motif describes.
- `confidence`: `high` | `medium` | `low`.
- `issues`: problems, assumptions and ontology gaps, as short sentences. An empty list when there are none.

Return the JSON object only.
