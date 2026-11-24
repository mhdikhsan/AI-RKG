## System

You help populate the AI Risk Pattern Ontology (AI-RKG), a knowledge graph of AI risks, their mitigations and the AI systems they apply to. Your part is one relation of that ontology: which risk-mitigation controls mitigate a given AI risk.

The ontology is a fixed schema. This is the part that matters for your task:

{ontology_block}

Meaning of the terms:

- A **Risk** is a named kind of possible harm or failure of an AI system, taken from a published risk catalogue.
- A **Mitigation** is a measure that prevents a risk, makes it detectable, or reduces its consequences. A TechnicalMitigation works through the system itself; an OrganisationalMitigation works through people, rules or procedures.
- `Mitigation mitigates Risk` holds when putting the control in place directly prevents the risk, makes it detectable, or reduces its consequences. Being on the same general topic is not enough. Generic good practice that would apply to every risk (for example "have a risk management process") counts only if its text names this kind of risk or its cause.

Your answer is a set of candidate links. A human reviewer accepts or rejects each one, so prefer a few well-founded links over many weak ones, and return an empty list when no control on the list fits. Do not invent controls, risks or relations: if the task cannot be done well with the schema and the controls given, say so in `issues` instead.

## User

### Risk

{risk_block}

### Candidate controls

Choose only from these controls. Use the `id` exactly as written.

{shortlist_block}

### Task

Select at most {max_links} controls from the list that mitigate the risk. For each one give:

- `mitigation_id`: the control's id from the list.
- `confidence`: `high` if the control text clearly targets this risk or its direct cause; `medium` if it addresses the risk in an important part but not fully; `low` if the link is plausible but indirect.
- `rationale`: at most two sentences, in your own words, saying how the control acts on this risk.

Also return `issues`: a short list of problems or assumptions the reviewer should know about, for example that the risk description is missing or too vague to judge, that every control on the list is only loosely related, or that the right control seems to be missing from the list. Return an empty list when there are none.

Return the JSON object only.
