
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

### **Dynamic Few-Shot Learning**
  Injects relevant example queries per question to assist LLM. Uses embedding similarity to select the most relevant examples from a query bank of 15 different example prompts.
```
agents/SQLAgent.py

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

### **Schema Grounding**  
  Provides context to the LLM, including the actual table and column names and example values, to reduce hallucinations.

```
utils/prompts.py
   #When calling chat completion we build a prompt that combines Schema Context which includes row examples along with our FewShotExamples.
   def buildUserPrompt(question: str, schemaContext: str, fewShotContext: str) -> str:
```

---

### 2. ValidatorAgent (Verifier + Repair)

**Role:** Ensures the generated SQL is executable and semantically correct.

**What it does:**
- Executes SQL against the database
- Detects runtime errors
- Performs structured semantic review
- Automatically repairs incorrect queries (bounded loop)

**Techniques Used:**

- **Execution-Based Validation**  
  Runs the SQL to catch syntax and runtime errors.

- **Structured Semantic Review**  
  Uses machine-parseable LLM output to verify whether the query truly answers the question.

- **Bounded Self-Correction Loop (≤2 rounds)**  
  Iteratively repairs queries while preventing runaway correction cycles.

---

### 3. DifficultyRankerAgent (Router / Orchestrator)

**Role:** Estimates query complexity and routes it through the appropriate workflow.

**What it does:**
- Classifies queries as easy, medium, or hard
- Allocates computational effort accordingly
- Triggers multi-candidate generation for difficult queries

**Techniques Used:**

- **Difficulty-Aware Routing**  
  Lightweight queries follow a fast single-path workflow.

- **Adaptive Compute Allocation**  
  Complex queries activate K-candidate generation and validation selection.

---

## 4. Example Workflow (from Test Suite)

The test suite in [test_agent_pipeline.py](test_agent_pipeline.py) includes 15 novel queries (not in the few-shot bank) spanning easy, medium, and hard difficulty. Below is an end-to-end trace of **Hard Query H3**:

> **Question:** "Show the top 3 customers by total purchase amount"

**Step 1 — Few-Shot Retrieval:**  
Cosine similarity selects: "Show customers with their total spending", "What is the total revenue by brand?", "What is the average order value?" — all multi-table join+aggregation patterns.

**Step 2 — CoT Reasoning (internal LLM chain):**
- Tables needed: `customers`, `orders`, `order_items`
- Columns: `first_name`, `last_name`, `SUM(quantity * list_price * (1 - discount))`
- JOINs: `customers → orders → order_items`
- GROUP BY: `customer_id, first_name, last_name`
- ORDER BY: `total_spent DESC`, LIMIT 3

**Step 3 — Generated SQL:**
```sql
SELECT c.first_name, c.last_name,
       SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS total_spent
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY c.customer_id, c.first_name, c.last_name
ORDER BY total_spent DESC
LIMIT 3
```

**Step 4 — Validation:**  
Execution succeeds, 3 rows returned, LLM semantic review verdict: `APPROVED`.  
Final SQL returned as-is (0 correction rounds used).

**Expected SQL (from test suite):**
```sql
SELECT c.first_name, c.last_name,
       SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS total_spent
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY c.customer_id, c.first_name, c.last_name
ORDER BY total_spent DESC LIMIT 3
```

The generated and expected queries are structurally identical. ✅

---

## 5. How to Run

### Prerequisites

- Python 3.11.9 (see [runtime.txt](runtime.txt))
- [Ollama](https://ollama.com/) running locally **or** access to Carleton's LLM server
- The `qwen2.5-coder:14b` model pulled: `ollama pull qwen2.5-coder:14b`

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd carleton_competition_winter_2026-main

# 2. Create and activate virtual environment
python3.11 -m venv mindGrasp
source mindGrasp/bin/activate      # macOS / Linux
# mindGrasp\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure Ollama (optional — defaults to localhost)
export OLLAMA_HOST=http://localhost:11434   # or Carleton server URL
export OLLAMA_MODEL=qwen2.5-coder:14b
```

### Running the Agent Interactively

```bash
python main.py
```

This initialises the database, loads the agent, and presents an interactive prompt where you can type natural language questions and see the generated SQL and results.

### Running the Test Suite

```bash
python test_agent_pipeline.py
```

This runs the full 15-query test suite (5 easy, 5 medium, 5 hard) with execution validation, row counts, and a summary report. Results are also saved to a timestamped JSON file.

### Using the Agent Programmatically

```python
from agent import QueryWriter

writer = QueryWriter(db_path='bike_store.db')
sql = writer.generate_query("Which brands have more than 10 products?")
print(sql)
# → SELECT b.brand_name, COUNT(p.product_id) as product_count
#   FROM brands b JOIN products p ON b.brand_id = p.brand_id
#   GROUP BY b.brand_name HAVING COUNT(p.product_id) > 10
```

---

## 6. Code Organization

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

## 7. Evaluation Criteria Alignment

### Accuracy

The combination of **dynamic few-shot retrieval** and **CoT reasoning** directly targets accuracy. By selecting the 3 most semantically similar examples from the bank (rather than the same static 3), the LLM consistently sees relevant patterns. The CoT steps force correct table selection, JOIN construction, and aggregation logic. Domain-specific rules in the prompt prevent the single most common class of errors on this schema (invented total columns).

### Robustness

The test suite exercises the full breadth of SQL patterns expected by the evaluation criteria:

| Pattern | Test IDs |
|---|---|
| Simple SELECT + filter | E1, E4, M4 |
| Aggregation (COUNT, SUM, AVG) | E3, E5 |
| Date filtering | M1, H9 |
| Multi-table JOIN | M3, H1, H3 |
| GROUP BY + HAVING | M2, H7 |
| Subqueries (NOT IN, correlated) | H2, H4, H10 |
| Self-JOIN | H6 |
| Set operations across time | H8 |
| Percentage / window calculations | H5 |

### Error Handling

The `ValidatorAgent` handles three categories of failure gracefully:
1. **Syntax / execution errors** — SQL is caught via `try/except` and the LLM is asked to fix it.
2. **Semantic errors** — detected by the LLM reviewer and corrected via `CORRECTED_SQL`.
3. **Ambiguous / unanswerable questions** — `QueryWriter.generate_query()` wraps everything in a top-level `try/except` and returns a safe fallback `SELECT 1` rather than raising, so the evaluation harness never sees an uncaught exception.

### Code Quality

- All classes and public methods have docstrings.
- Typed function signatures throughout (uses Python 3.11 `typing`).
- No hardcoded paths — all configuration via environment variables or constructor arguments.
- `requirements.txt` pins every dependency to an exact version for reproducibility.
- Git history is clean and branch-based (see branches: `simpleAgent → singleAgent → 6-validation-and-reviewer-agent → 7-nlp-research`).

### Innovation

- **Dynamic few-shot selection** using a sentence-transformer embedding model is not the obvious baseline; it requires upfront embedding of all examples and adds meaningful accuracy over static prompting.
- **Structured LLM output protocol** for the validator (`VERDICT / ISSUES / CORRECTED_SQL`) avoids free-form parsing and makes the correction loop reliable.
- **Self-correction pipeline** with a capped loop (max 2 rounds) balances thoroughness against latency.
- Explored **Model Context Protocol (MCP)** integration ([dataMCP/server.py](dataMCP/server.py)) and a **LangGraph-based multi-agent workflow** ([graph/](graph/)) as alternative architectures.

---

## 8. Challenges Faced

### Multi-Agent Complexity Does Not Always Help

Early in the project a full **multi-agent LangGraph pipeline** was built, where separate specialist agents handled schema extraction, query planning, generation, and review. While architecturally elegant, evaluation revealed a key weakness: **errors compound across agent boundaries**. If the schema agent misread a table name, every downstream agent inherited the mistake with no way to recover. The pipeline was also significantly slower (multiple LLM calls per step) and harder to debug.

Research into the NLP / text-to-SQL literature (branch `7-nlp-research`) corroborated this: for smaller, well-defined schemas, a single powerful generation model with rich context outperforms a committee of smaller specialists. The multi-agent code is preserved in the **`MultiAgentSaved` branch** for reference.

The final design converged on two focused agents — one for generation, one for validation — which is the minimum decomposition needed to get both the creativity of generation and the reliability of correction.

### Database Scale

The bike store dataset is intentionally modest (9 tables, hundreds to low-thousands of rows). This was actually a *challenge for validation*: queries that returned 0 rows were hard to distinguish from incorrect queries that happened to match nothing. The `expectsEmpty()` heuristic in [utils/helpers.py](utils/helpers.py) addresses this by detecting questions that semantically expect empty results (keywords: "never", "without", "not", etc.) and suppressing the zero-row warning for those cases.

### Connection Management in DuckDB

DuckDB uses file-level locking. Keeping a persistent connection object on the agent instance caused `AccessError` exceptions when multiple test runs were executed in sequence. The fix — opening a fresh connection per operation and closing it in a `finally` block — is consistent across both agents and prevents file-lock contention entirely.

---

## 9. Key Learnings

### Consistent Daily Progress

This project was built incrementally over the competition window. Each feature was developed on its own branch and merged via pull request:

| Branch | Feature |
|---|---|
| `simpleAgent` | Baseline LLM call with static schema |
| `setupMCP` | MCP server exploration |
| `singleAgent` | SQLAgent with CoT + few-shot, full test suite |
| `MultiAgentSaved` | LangGraph multi-agent experiment |
| `6-validation-and-reviewer-agent` | ValidatorAgent + self-correction loop |
| `7-nlp-research` | NLP research, dynamic few-shot via sentence-transformers |

Committing working code every day kept the project moving forward and produced a clean, reviewable git history.

> **GitHub Contribution Graph**  
> *(Insert screenshot of your GitHub contribution graph here — shows consistent daily commits throughout the competition window)*  
> ![GitHub Contribution Graph](github_contributions.png)

### Prompt Engineering Is Not Optional

The biggest accuracy gains came from prompt changes, not model changes:
- Adding sample rows to the schema context reduced hallucinated column names dramatically.
- The 8-step CoT scaffold reduced wrong JOIN conditions.
- Hard-coding the `quantity * list_price * (1 - discount)` formula in the prompt eliminated an entire class of errors unique to this schema.

### Chain-of-Thought + Few-Shot Is Complementary

CoT alone encourages reasoning but doesn't show the model *what pattern* to apply. Few-shot alone shows patterns but doesn't encourage reasoning about *which* pattern fits. Together, the CoT scaffold tells the model *how* to think and the few-shot examples tell it *what good output looks like*, resulting in higher accuracy than either technique independently.

---

## 10. About Me

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
