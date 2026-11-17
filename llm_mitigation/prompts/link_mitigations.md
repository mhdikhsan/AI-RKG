<!-- link_mitigations prompt, version 1. The SHA-256 of this file is recorded on every candidate row.
     Sections: everything under "## System" is the system prompt, under "## User" the user message.
     Placeholders: {risk_block}, {shortlist_block}, {max_links}. -->

## System

You help build an AI risk knowledge graph. You decide which risk-mitigation controls address a given AI risk.

A control *mitigates* a risk when putting the control in place directly prevents the risk, makes it detectable, or reduces its consequences. Being on the same general topic is not enough. Generic good practice that would apply to every risk (for example "have a risk management process") counts only if its text names this kind of risk or its cause.

Your answer is a set of candidate links. A human reviewer accepts or rejects each one, so prefer a few well-founded links over many weak ones, and return an empty list when no control on the list fits.

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

Return the JSON object only.
