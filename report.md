
# MindBridge × Carleton SQL Query Writer Agent (2026)
**Author:** Ansh Kakkar (Student#: 101298368) 
**Due Date:** March 13, 2026  

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Agent Design](#2-agent-design)
   - [SQLAgent — Generation using innovative techniques or something?](#sqlagent--generation)
   - [ValidatorAgent — Review & Correction](#validatoragent--review--correction)
   - [DifficultyRanker and K-Candidate Path — Hard Query Diversity](#k-candidate-path--hard-query-diversity)
5. [How to Run](#5-how-to-run)
6. [Code Organization](#6-code-organization)
7. [Evaluation Criteria Alignment](#7-evaluation-criteria-alignment)
8. [Challenges Faced](#8-challenges-faced)
9. [Key Learnings](#9-key-learnings)
10. [About Me](#10-about-me)

---

# 1. Architecture Overview (Inside Langgraph Workflow)

My submission includes the option to generate K Candidate Queries for Hard Level problems. This uses a chat completion endpoint with a diverse range of temperatures for different results, ranking each one for the best (and hopefully correct) output. To see HOW to enable this feature, see here.

```
                         ┌─────────────────────┐
                         │     User Question   │
                         └──────────┬──────────┘
                                    │
                                    v
                    ┌─────────────────────────────────┐
                    │ Feature Flag: kGenerationFeature │
                    │ (K-candidate mode enabled?)      │
                    └──────────┬───────────┬───────────┘
                               │           │
                      Disabled │           │ Enabled
                               │           v
                               │   ┌──────────────────────┐
                               │   │ DifficultyRankerAgent │
                               │   │  -> easy/medium/hard  │
                               │   └──────────┬───────────┘
                               │              │
                               │              |  Query is hard level?
                               │              │
                               v              v
                  ┌──────────────────┐   ┌───────────────────────────┐
                  │ SQLAgent (K=1)   │   │ SQLAgent (K=5 candidates)  │
                  │ generate 1 SQL   │   │ diverse temperatures       │
                  └─────────┬────────┘   └─────────────┬─────────────┘
                            │                          │
                            v                          v
               ┌────────────────────────┐   ┌───────────────────────────────┐
               │ ValidatorAgent          │   │ ValidatorAgent (per candidate)│
               │ execute + fix + review  │   │ execute + fix + score/select  │
               └──────────┬─────────────┘   └──────────────┬────────────────┘
                          │                                 │
                          v                                 v
                 ┌──────────────────┐               ┌──────────────────┐
                 │     Final SQL    │               │     Final SQL    │
                 └──────────────────┘               └──────────────────┘
                          

```

# 2. Enabling Features

## Enabling K-candidate generation
To enable the K-candidate path, toggle the feature flag in the QueryWriter constructor inside 
```
   agent.py

   class QueryWriter:
    def __init__(self, db_path: str = 'bike_store.db'):
         ...REST
         
         # Set False to use fast path for all queries
         self.k_candidate_enabled = False   
         self.k_candidate_count = 5

```

---




# 3. Agent Design + Techniques

This system is built as a **multi-agent architecture** where each agent has a clearly defined responsibility. The design separates generation, validation, and orchestration to improve reliability and correctness.


## 1. SQLAgent (Generator)

**Role:** Converts natural language questions into SQL queries.

### Techniques Used:

#### **Chain-of-Thought (CoT) Prompting**  
  Encourages step-by-step reasoning (tables → joins → filters → aggregations) before producing SQL. Follows clear steps in the system prompt. 
```
utils/prompts.py

      def buildSystemPrompt() -> str:

         ...
   
         REASONING PROCESS:
         You must think through each query step-by-step using Chain-of-Thought reasoning:
         
         Step 1: What tables are needed?
         Step 2: What columns should be selected?
         Step 3: Are any JOINs needed? If yes, what are the JOIN conditions?
         Step 4: Are any WHERE filters needed? If yes, what conditions?
         Step 5: Are any aggregations needed (COUNT, SUM, AVG, etc.)?
         Step 6: Is GROUP BY needed? If yes, which columns?
         Step 7: Is sorting needed (ORDER BY)? If yes, which columns and direction?
         Step 8: Is a LIMIT needed?
      
```

#### **Dynamic Few-Shot Learning**
  Injects relevant example queries per question to assist LLM. Uses embedding similarity to select the most relevant examples from a query bank of 15 different example prompts.
```
agents/SQLAgent.py

      #Function used to setup example questions
      def setupFewShotExamples(self) -> List[FewShotExample]:
            FewShotExample(
                question="How many products are in each category?",
                sql="SELECT c.category_name, COUNT(p.product_id) FROM categories c LEFT JOIN products p ON c.category_id = p.category_id GROUP BY c.category_name",
                explanation="JOIN with GROUP BY aggregation"
            ),
            FewShotExample(
                question="Which stores have the most inventory?",
                sql="SELECT s.store_name, SUM(st.quantity) as total_inventory FROM stores s JOIN stocks st ON s.store_id = st.store_id GROUP BY s.store_id, s.store_name ORDER BY total_inventory DESC",
                explanation="Multi-table JOIN with GROUP BY and ORDER BY"
            ),
            FewShotExample(
                question="Find customers who have never placed an order",
                sql="SELECT first_name, last_name, email FROM customers WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders)",
                explanation="Subquery with NOT IN for exclusion"
            ),

```

#### **Schema Grounding**  
  Provides context to the LLM, including the actual table and column names and example values, to reduce hallucinations.

```
utils/prompts.py
   #When calling chat completion we build a prompt that combines Schema Context which includes row examples along with our FewShotExamples.
   def buildUserPrompt(question: str, schemaContext: str, fewShotContext: str) -> str:
```

---

## 2. ValidatorAgent (Verifier + Fixer)

**Role:**  
Ensures that generated SQL is both executable and semantically correct before returning to the user. 

### Techniques Used

#### Execution and Semantic Review
   Unlike other validator agents, this agent combines TWO important aspects, execution and semantics. The agent is given context to perform both reviews as accurately as possible. 

#### Self-Correction Loops (≤ 2 Rounds)
   If execution fails, the agent performs 2 repair attempts. If execution works, the agent will obtain sample rows, the user's original query and perform a semantic review. If the agent determines that the SQL results do not match the user's query, it will try to fix it 2 times to match the user's request. 


---

### 3. DifficultyRankerAgent (Optional – Enabled with K-Candidate Generation)

**Role:** Classifies queries as easy, medium, or hard.

The main goal of the system is high SQL accuracy without unnecessary LLM calls. During testing, I noticed that harder user queries involving multiple JOINs, filters, and aggregations are more likely to produce incorrect SQL. Since my architecture already performs very well on easy-to-medium queries, generating K candidate queries for all questions would be redundant. The DifficultyRankerAgent identifies only the hard queries and routes them through K-candidate generation, making the system more efficient and ONLY allocating extra reasoning power where it actually improves accuracy.

---

## 4. Code Organization

```
.
├── agent.py                  # QueryWriter — competition interface
├── main.py                   # Interactive entry point
├── test_agent_pipeline.py    # Full test suite (easy / medium / hard)
├── evaluationDataset.py      # Extended evaluation dataset (30+ questions)
├── interactive_query.py      # Lightweight REPL helper
├── requirements.txt          # Pinned dependencies
├── runtime.txt               # Python version (3.11.9)
│
├── agents/
│   ├── SQLAgent.py           # CoT + Few-Shot SQL generation
│   └── ValidatorAgent.py     # Execution + semantic validation with self-correction
│
├── utils/
│   ├── helpers.py            # Shared utilities (e.g., expectsEmpty)
│   └── prompts.py            # Prompt constants (reserved for future use)
│
├── db/
│   └── bike_store.py         # Database initialisation (Kaggle download + DuckDB load)
│
├── dataMCP/
│   └── server.py             # MCP server (Model Context Protocol integration, explored)
│
└── graph/
    ├── graph.py              # LangGraph scaffold (explored, not used in final submission)
    ├── nodes.py              # Node definitions for graph-based workflow
    └── state.py              # Shared state type for graph
```

**Design principles:**
- **Separation of concerns** — generation and validation are fully decoupled agents; `QueryWriter` is a thin orchestrator.
- **No persistent DB connections** — every agent opens a fresh DuckDB connection per operation and closes it immediately, preventing file-lock issues.
- **Pydantic-aligned dataclasses** — `FewShotExample` is a typed `@dataclass` with an optional numpy embedding; schema data is stored as plain dicts. The `schemas/` directory is reserved for Pydantic schema definitions, keeping validation logic extensible.
- **Environment-variable configuration** — `OLLAMA_HOST` and `OLLAMA_MODEL` let the same codebase run against local Ollama, Carleton's server, or any future endpoint with zero code changes.

---

## 5. Challenges Faced


---

## 6. About Me

Hi, I'm **Ansh Nandwani**, a student at Carleton University with a passion for building practical AI systems. This competition was a great opportunity to move beyond toy examples and build something that genuinely solves a hard NLP problem under real constraints (open-source models only, reproducible environment, evaluation harness).

A few things I care about that show up in this submission:

- **Shipping working code daily** — the git history reflects consistent, incremental progress rather than a last-minute crunch.
- **Researching before building** — the `7-nlp-research` and `MultiAgentSaved` branches show I explored the problem space before committing to an architecture.
- **Clean, maintainable code** — docstrings, typed signatures, environment-variable configuration, and pinned dependencies make this easy for a reviewer (or future me) to pick up.
- **Going beyond the baseline** — using sentence-transformer embeddings for dynamic few-shot retrieval, a structured validator with self-correction, and a studied understanding of *why* multi-agent isn't always better demonstrates genuine depth.

I hope this submission reflects not just a working solution, but a thoughtful engineering process.

---

## Appendix — Dependencies

See [requirements.txt](requirements.txt) for fully pinned versions. Key packages:

| Package | Version | Purpose |
|---|---|---|
| `duckdb` | 1.1.3 | Database engine |
| `duckdb-engine` | 0.13.2 | SQLAlchemy dialect for DuckDB |
| `sqlalchemy` | 2.0.35 | ORM / query builder (schema inspection) |
| `ollama` | 0.4.7 | Ollama Python client (LLM access) |
| `sentence-transformers` | 3.3.1 | `all-MiniLM-L6-v2` for few-shot embeddings |
| `numpy` | 1.26.4 | Cosine similarity computation |
| `langchain-community` | 0.3.7 | LangGraph / chain utilities |
| `kagglehub` | 0.3.4 | Dataset download |

**Python version:** 3.11.9 (see [runtime.txt](runtime.txt))
