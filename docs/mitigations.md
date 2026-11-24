To produce Categorized_Mapped_Risk_Mitigation_Table 

Input : https://github.com/IBM/ai-atlas-nexus/blob/main/src/ai_atlas_nexus/data/knowledge_graph/risk_atlas_data.yaml 

And MIT mitigation database 

 

Mitigation Mapping Process 

The experimental process of connecting the AI Risk Taxonomy to the Mitigation Database relies on a programmatic Natural Language Processing (NLP) pipeline to evaluate semantic relevance rather than relying on manual keyword matching. 

 

Here is the step-by-step methodology used to produce the mapped datasets: 

 

Data Ingestion & Cleaning: The process extracts the core textual fields from both datasets. For the risks, it concatenates the name, description, and concern fields. For the mitigations, it concatenates the Action Name and Action Definition. Missing values are dropped or forward-filled to ensure clean text. 

Semantic Vectorization (TF-IDF): The combined text fields are passed through a TF-IDF (Term Frequency-Inverse Document Frequency) vectorizer. This algorithm translates the natural language of the risks and mitigations into numerical vectors, assigning higher mathematical weight to unique, context-heavy words while filtering out common English stop words. 

Cosine Similarity Scoring: The system calculates the cosine similarity between every risk vector and every mitigation vector. This creates a scoring matrix representing the contextual distance (or "relevance") between each risk and every possible mitigation strategy. 

Thresholding & Top-K Filtering: To eliminate statistical noise and false positives, a strict similarity floor is applied (Cosine Similarity > 0.05). From the passing scores, the algorithm isolates exactly the Top 3 highest-scoring mitigations per risk to maintain a concise, prioritized 1-to-3 mapping density. 

Rule-Based Categorization: Overarching control categories are dynamically assigned to the mitigations based on the numerical prefix of their assigned MitigationCode (e.g., 1 = Governance, 2 = Technical, 3 = Operational, 4 = Transparency). 

Dynamic Justification Generation: Instead of generating generic AI text, the script programmatically extracts the first logical sentence of the risk's core concern and the first logical sentence of the mitigation's Action Definition, injecting them into a rigid explanatory template to explicitly justify the semantic match. 

Multi-Format Export: The finalized relationships are exported into a flat CSV (incorporating all prefixed primary fields and categorized secondary fields) and a nested hierarchical YAML file for structured database ingestion. 

Prompt Used to Reproduce the Experiment 

To reproduce the most complete, advanced version of this experiment (including the categorization logic, the TF-IDF thresholding instructions, and the elaborated justification logic) across any generic tabular datasets, use the following comprehensive prompt: 

 

Given two datasets—one containing a Primary Risk Taxonomy and the other containing a Secondary Mitigation Taxonomy—create a mapped dataset that connects each item from the primary risk taxonomy to its corresponding appropriate item(s) in the secondary mitigation taxonomy, based on contextual and semantic relevance. 

 

Please produce a mapped CSV table with the following structure and logic: 

 

1. CSV Table Structure: 

 

From the Primary Taxonomy: Include all original fields present in the risk dataset (e.g., id, name, description, concern, etc.). Prefix these column headers with "Primary " (e.g., "Primary Id", "Primary Name"). 

From the Secondary Taxonomy: Include the Action ID and Action Definition. Rename the "Action Name" column to Mitigation Action Name. 

Sub Category: Include the "MitigationCode" (or equivalent code column) from the secondary taxonomy and name the column Sub Category. 

Category: Create a new Category column based on the starting number of the Sub Category (MitigationCode) using the following mapping rules: 

If it starts with 1 ➔ 1. Governance & Oversight Controls 

If it starts with 2 ➔ 2. Technical & Security Controls 

If it starts with 3 ➔ 3. Operational Process Controls 

If it starts with 4 ➔ 4. Transparency & Accountability Controls 

 

2. Additional Constraints: 

Take into consideration that this is a many-to-many relationship: a primary item might require multiple secondary strategies, and a single secondary strategy could apply to multiple primary items. 

Map exactly the top 3 most relevant connections for each risk item based on semantic and contextual similarity (using techniques like TF-IDF and Cosine Similarity) with a minimum similarity threshold of 0.05. Keep the outputs comprehensive yet concise. 