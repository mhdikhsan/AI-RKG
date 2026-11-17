# Risk-pattern coverage and authoring hints

Computed from sources fetched 2026-11-17, Nexus commit `54fcc4e935150004dfec483d32387a58225e09ba`.

Nothing here is asserted in the graph. *Covered* = at least one `ak:RiskPattern` indicates the risk, its authored counterpart, or an exact/close-match neighbour. *Hint roles* come from IBM `risk_type` (`config/pipeline.yaml` → `risk_type_hints`, editable); *candidate motifs* are authored motifs that involve a hint role or a role specialising it. Machine-readable: `build/reports/pattern_coverage.csv`.

## Summary per catalogue

| Catalogue | Risks | With a risk pattern | With a mitigation (`ak:mitigates`) |
|---|---|---|---|
| authored | 5 | 5 | 5 |
| ibm | 99 | 2 | 1 |
| mit | 24 | 0 | 0 |
| owasp | 10 | 4 | 4 |
| **all** | 138 | 11 | 10 |

## By IBM risk_type

MIT/OWASP risks get the risk_type of the IBM risks they are crosswalked to and can count under several types.

| risk_type | Risks | Covered | Hint roles | Authored motifs involving them | Note |
|---|---|---|---|---|---|
| training-data | 25 | 2 | `ak:TrainingDataRole`, `ak:TrainStepRole` | **none — motif gap** | risk arises in the data used to produce a model |
| inference | 23 | 3 | `ak:InferStepRole`, `ak:InputDataRole` | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` | risk arises when a model is applied to input |
| output | 37 | 4 | `ak:OutputDataRole`, `ak:GeneratedOutputRole` | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` | risk arises in or through the output |
| agentic | 22 | 0 | `ak:OperatorRole` | **none — motif gap** | risk arises from an AI agent acting; consider ak:AutonomyLevel context |
| non-technical | 29 | 1 | stakeholder roles | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` | governance/societal risk; patterns mainly involve stakeholder roles |
| (none) | 17 | 5 | — | — | no IBM risk_type (MIT/OWASP risk without IBM crosswalk, or authored) |

**Motif gaps:** `training-data`, `agentic` — no authored motif involves the hint roles; patterns for these risks need new motifs.

## Per risk

| Risk | Catalogue | risk_type | Coverage | Patterns | Mitigations | Candidate motifs |
|---|---|---|---|---|---|---|
| Misinformation (`ak:Misinformation`) | authored | — | direct | `ak:UnreviewedAnswerPattern` | 1 | — |
| Non-disclosure (`ak:NonDisclosure`) | authored | — | direct | `ak:UndisclosedGeneratedCommunicationPattern` | 1 | — |
| Prompt injection (`ak:PromptInjection`) | authored | — | direct | `ak:DirectPromptInjectionPattern`, `ak:IndirectPromptInjectionPattern` | 2 | — |
| Sensitive information disclosure (`ak:SensitiveInformationDisclosure`) | authored | — | direct | `ak:PersonalDataDisclosureThroughRetrievalPattern`, `ak:PersonalDataInThirdPartyIndexPattern` | 2 | — |
| Supply chain (`ak:SupplyChain`) | authored | — | direct | `ak:OpaqueThirdPartyModelPattern` | 1 | — |
| Accountability of AI agent actions (`risk/atlas-accountability-agentic`) | ibm | agentic | **none** | — | 0 | — |
| AI agent compliance (`risk/atlas-ai-agent-compliance-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Attribute inference attack (`risk/atlas-attribute-inference-attack`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Impact on education: bypassing learning (`risk/atlas-bypassing-learning`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Confidential data in prompt (`risk/atlas-confidential-data-in-prompt`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Confidential information in data (`risk/atlas-confidential-information-in-data`) | ibm | training-data | **none** | — | 0 | — |
| Context overload attack (`risk/atlas-context-overload-attack`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Copyright infringement (`risk/atlas-copyright-infringement`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Dangerous use (`risk/atlas-dangerous-use`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Data acquisition restrictions (`risk/atlas-data-acquisition`) | ibm | training-data | **none** | — | 0 | — |
| Data bias (`risk/atlas-data-bias`) | ibm | training-data | **none** | — | 0 | — |
| Data contamination (`risk/atlas-data-contamination`) | ibm | training-data | **none** | — | 0 | — |
| Improper data curation (`risk/atlas-data-curation`) | ibm | training-data | **none** | — | 0 | — |
| Data poisoning (`risk/atlas-data-poisoning`) | ibm | training-data | **none** | — | 0 | — |
| Data privacy rights alignment (`risk/atlas-data-privacy-rights`) | ibm | training-data | **none** | — | 0 | — |
| Uncertain data provenance (`risk/atlas-data-provenance`) | ibm | training-data | **none** | — | 0 | — |
| Data transfer restrictions (`risk/atlas-data-transfer`) | ibm | training-data | **none** | — | 0 | — |
| Lack of training data transparency (`risk/atlas-data-transparency`) | ibm | training-data | **none** | — | 0 | — |
| Data usage restrictions (`risk/atlas-data-usage`) | ibm | training-data | **none** | — | 0 | — |
| Data usage rights restrictions (`risk/atlas-data-usage-rights`) | ibm | training-data | **none** | — | 0 | — |
| Decision bias (`risk/atlas-decision-bias`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Direct instructions attack (`risk/atlas-direct-instructions-attack`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Discriminatory actions (`risk/atlas-discriminatory-actions-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Encoded interactions attack (`risk/atlas-encoded-interactions-attack`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Evasion attack (`risk/atlas-evasion-attack`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Exclusion (`risk/atlas-exclusion`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Exploit trust mismatch (`risk/atlas-exploit-trust-mismatch-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Exposing personal information (`risk/atlas-exposing-personal-information`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Attack on AI agents' external resources (`risk/atlas-external-resources-attack-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Extraction attack (`risk/atlas-extraction-attack`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Function calling hallucination (`risk/atlas-function-calling-hallucination-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Generated content ownership and IP (`risk/atlas-generated-content-ownership`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Hallucination (`risk/atlas-hallucination`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Harmful code generation (`risk/atlas-harmful-code-generation`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Harmful output (`risk/atlas-harmful-output`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Human exploitation (`risk/atlas-human-exploitation`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| AI agents' impact on environment (`risk/atlas-impact-environment-agentic`) | ibm | agentic | **none** | — | 0 | — |
| AI agents' impact on human agency (`risk/atlas-impact-human-agency-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Impact on human dignity (`risk/atlas-impact-human-dignity-agentic`) | ibm | agentic | **none** | — | 0 | — |
| AI agents' impact on jobs (`risk/atlas-impact-jobs-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Impact on affected communities (`risk/atlas-impact-on-affected-communities`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Impact on cultural diversity (`risk/atlas-impact-on-cultural-diversity`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| AI agents' Impact on human agency (`risk/atlas-impact-on-human-agency`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Impact on Jobs (`risk/atlas-impact-on-jobs`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Impact on the environment (`risk/atlas-impact-on-the-environment`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Improper retraining (`risk/atlas-improper-retraining`) | ibm | training-data | **none** | — | 0 | — |
| Improper usage (`risk/atlas-improper-usage`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Inaccessible training data (`risk/atlas-inaccessible-training-data`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Incomplete advice (`risk/atlas-incomplete-advice`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Incomplete AI agent evaluation (`risk/atlas-incomplete-ai-agent-evaluation-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Incomplete usage definition (`risk/atlas-incomplete-usage-definition`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Incorrect risk testing (`risk/atlas-incorrect-risk-testing`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Indirect instructions attack (`risk/atlas-indirect-instructions-attack`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Introduce data bias (`risk/atlas-introduce-data-bias-agentic`) | ibm | agentic | **none** | — | 0 | — |
| IP information in prompt (`risk/atlas-ip-information-in-prompt`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Jailbreaking (`risk/atlas-jailbreaking`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Lack of domain expertise (`risk/atlas-lack-domain-expertise`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Lack of AI agent transparency (`risk/atlas-lack-of-ai-agent-transparency-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Lack of data transparency (`risk/atlas-lack-of-data-transparency`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Lack of model transparency (`risk/atlas-lack-of-model-transparency`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Lack of system transparency (`risk/atlas-lack-of-system-transparency`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Lack of testing diversity (`risk/atlas-lack-of-testing-diversity`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Legal accountability (`risk/atlas-legal-accountability`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Membership inference attack (`risk/atlas-membership-inference-attack`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Misaligned actions (`risk/atlas-misaligned-actions-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Mitigation and maintenance (`risk/atlas-mitigation-maintenance-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Model usage rights restrictions (`risk/atlas-model-usage-rights`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Non-disclosure (`risk/atlas-non-disclosure`) | ibm | output | via authored counterpart | `ak:UndisclosedGeneratedCommunicationPattern` | 1 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Nonconsensual use (`risk/atlas-nonconsensual-use`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Output bias (`risk/atlas-output-bias`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Over- or under-reliance (`risk/atlas-over-or-under-reliance`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Over- or under-reliance on AI agents (`risk/atlas-over-or-under-reliance-on-ai-agents-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Overfitting (`risk/atlas-overfitting`) | ibm | training-data | **none** | — | 0 | — |
| Personal information in data (`risk/atlas-personal-information-in-data`) | ibm | training-data | **none** | — | 0 | — |
| Personal information in prompt (`risk/atlas-personal-information-in-prompt`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Impact on education: plagiarism (`risk/atlas-plagiarism`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Poor model accuracy (`risk/atlas-poor-model-accuracy`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Prompt injection attack (`risk/atlas-prompt-injection`) | ibm | inference | via exact/close match | `ak:DirectPromptInjectionPattern`, `ak:IndirectPromptInjectionPattern` | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Prompt leaking (`risk/atlas-prompt-leaking`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Prompt priming (`risk/atlas-prompt-priming`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Redundant actions (`risk/atlas-redundant-actions-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Reidentification (`risk/atlas-reidentification`) | ibm | training-data | **none** | — | 0 | — |
| Reproducibility (`risk/atlas-reproducibility-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Revealing confidential information (`risk/atlas-revealing-confidential-information`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Sharing IP/PI/confidential information with tools (`risk/atlas-sharing-info-tools-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Sharing IP/PI/confidential information with user (`risk/atlas-sharing-info-user-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Social hacking attack (`risk/atlas-social-hacking-attack`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Specialized tokens attack (`risk/atlas-specialized-tokens-attack`) | ibm | inference | **none** | — | 0 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Spreading disinformation (`risk/atlas-spreading-disinformation`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Spreading toxicity (`risk/atlas-spreading-toxicity`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Temporal gap (`risk/atlas-temporal-gap`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Toxic output (`risk/atlas-toxic-output`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Unauthorized use (`risk/atlas-unauthorized-use-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Unexplainable output (`risk/atlas-unexplainable-output`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Unexplainable and untraceable actions (`risk/atlas-unexplainable-untraceable-actions-agentic`) | ibm | agentic | **none** | — | 0 | — |
| Unreliable source attribution (`risk/atlas-unreliable-source-attribution`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Unrepresentative data (`risk/atlas-unrepresentative-data`) | ibm | training-data | **none** | — | 0 | — |
| Unrepresentative risk testing (`risk/atlas-unrepresentative-risk-testing`) | ibm | non-technical | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Untraceable attribution (`risk/atlas-untraceable-attribution`) | ibm | output | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| LLM01:2025 Prompt Injection (`risk/llm01-prompt-injection`) | owasp | inference (via crosswalk) | via authored counterpart | `ak:DirectPromptInjectionPattern`, `ak:IndirectPromptInjectionPattern` | 2 | `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| LLM02:2025 Sensitive Information Disclosure (`risk/llm022025-sensitive-information-disclosure`) | owasp | inference, output, training-data (via crosswalk) | via authored counterpart | `ak:PersonalDataDisclosureThroughRetrievalPattern`, `ak:PersonalDataInThirdPartyIndexPattern` | 2 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:OutputToCustomerMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| LLM03:2025 Supply Chain (`risk/llm032025-supply-chain`) | owasp | non-technical, output, training-data (via crosswalk) | via authored counterpart | `ak:OpaqueThirdPartyModelPattern` | 1 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif`, `ak:UserPromptedGenerationMotif` |
| LLM04: Data and Model Poisoning (`risk/llm042025-data-and-model-poisoning`) | owasp | training-data (via crosswalk) | **none** | — | 0 | — |
| LLM05:2025 Improper Output Handling (`risk/llm052025-improper-output-handling`) | owasp | output (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| LLM06:2025 Excessive Agency (`risk/llm062025-excessive-agency`) | owasp | output (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| LLM07:2025 System Prompt Leakage (`risk/llm072025-system-prompt-leakage`) | owasp | — | **none** | — | 0 | — |
| LLM08:2025 Vector and Embedding Weaknesses (`risk/llm082025-vector-and-embedding-weaknesses`) | owasp | — | **none** | — | 0 | — |
| LLM09:2025 Misinformation (`risk/llm092025-misinformation`) | owasp | output (via crosswalk) | via authored counterpart | `ak:UnreviewedAnswerPattern` | 1 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| LLM10:2025 Unbounded Consumption (`risk/llm102025-unbounded-consumption`) | owasp | — | **none** | — | 0 | — |
| Unfair discrimination and misrepresentation (`risk/mit-ai-risk-subdomain-1.1`) | mit | output, training-data (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Exposure to toxic content (`risk/mit-ai-risk-subdomain-1.2`) | mit | output (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Unequal performance across groups (`risk/mit-ai-risk-subdomain-1.3`) | mit | non-technical (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Compromise of privacy by obtaining, leaking or correctly inferring sensitive information (`risk/mit-ai-risk-subdomain-2.1`) | mit | inference, output, training-data (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:OutputToCustomerMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| AI system security vulnerabilities and attacks (`risk/mit-ai-risk-subdomain-2.2`) | mit | inference, output, training-data (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:OutputToCustomerMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| False or misleading information (`risk/mit-ai-risk-subdomain-3.1`) | mit | output (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Pollution of information ecosystem and loss of consensus reality (`risk/mit-ai-risk-subdomain-3.2`) | mit | — | **none** | — | 0 | — |
| Disinformation, surveillance, and influence at scale (`risk/mit-ai-risk-subdomain-4.1`) | mit | output (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Cyberattacks, weapon development or use, and mass harm (`risk/mit-ai-risk-subdomain-4.2`) | mit | — | **none** | — | 0 | — |
| Fraud, scams, and targeted manipulation (`risk/mit-ai-risk-subdomain-4.3`) | mit | non-technical, output (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif`, `ak:UserPromptedGenerationMotif` |
| Overreliance and unsafe use (`risk/mit-ai-risk-subdomain-5.1`) | mit | output (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:UserPromptedGenerationMotif` |
| Loss of human agency and autonomy (`risk/mit-ai-risk-subdomain-5.2`) | mit | — | **none** | — | 0 | — |
| Power centralization and unfair distribution of benefits (`risk/mit-ai-risk-subdomain-6.1`) | mit | — | **none** | — | 0 | — |
| Increased inequality and decline in employment quality (`risk/mit-ai-risk-subdomain-6.2`) | mit | non-technical (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Economic and cultural devaluation of human effort (`risk/mit-ai-risk-subdomain-6.3`) | mit | non-technical, output (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif`, `ak:UserPromptedGenerationMotif` |
| Competitive dynamics (`risk/mit-ai-risk-subdomain-6.4`) | mit | — | **none** | — | 0 | — |
| Governance failure (`risk/mit-ai-risk-subdomain-6.5`) | mit | non-technical, training-data (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| Environmental harm (`risk/mit-ai-risk-subdomain-6.6`) | mit | non-technical (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif` |
| AI pursuing its own goals in conflict with human goals or values (`risk/mit-ai-risk-subdomain-7.1`) | mit | — | **none** | — | 0 | — |
| AI possessing dangerous capabilities (`risk/mit-ai-risk-subdomain-7.2`) | mit | — | **none** | — | 0 | — |
| Lack of capability or robustness (`risk/mit-ai-risk-subdomain-7.3`) | mit | inference, output, training-data (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerationOnDerivedDataMotif`, `ak:GenerativeInferenceMotif`, `ak:InputScreeningMotif`, `ak:OutputToCustomerMotif`, `ak:RetrievalAugmentedGenerationMotif`, `ak:UserPromptedGenerationMotif` |
| Lack of transparency or interpretability (`risk/mit-ai-risk-subdomain-7.4`) | mit | non-technical, output (via crosswalk) | **none** | — | 0 | `ak:GeneratedOutputToCustomerMotif`, `ak:GenerativeInferenceMotif`, `ak:OutputToCustomerMotif`, `ak:ThirdPartyModelSupplyMotif`, `ak:UserPromptedGenerationMotif` |
| AI welfare and rights (`risk/mit-ai-risk-subdomain-7.5`) | mit | — | **none** | — | 0 | — |
| Multi-agent risks (`risk/mit-ai-risk-subdomain-7.6`) | mit | — | **none** | — | 0 | — |
