
# MindBridge × Carleton SQL Query Writer Agent (2026)
**Author:** Ansh Kakkar (Student#: 101298368) 
**Due Date:** March 13, 2026  


## Table of Contents

1. [High Level Architecture Overview](#1-high-level-architecture-overview)
2. [Why My Solution Stands Out](#2-why-my-solution-stands-out)
3. [Handling Ambiguous & Irrelevant Queries](#3-handling-ambiguous--irrelevant-queries)
4. [Agent Design + Techniques](#4-agent-design--techniques)
5. [Enabling MultiConversational Mode](#5-enabling-multiconversational-feature)
6. [Code Organization](#6-code-organization)
7. [Challenges Faced](#7-challenges-faced)
8. [About Me](#8-about-me)

---

# 1. High Level Architecture Overview

My submission uses a **two-stage agentic pipeline** orchestrated by LangGraph:

- **SQLAgent (generateSqlNode)** — Uses ReAct loops and tool-use to reason about table relationships, verify column names/values, classify intent (Clear / Ambiguous / Irrelevant) and generate SQL. 

- **K-Candidate Generation & Validation (kCandidatesNode)** — Generates multiple SQL candidates at varied temperatures (0.7, 0.3, 1.0, 0.5, ...) and returns the first one passing execution and semantic validation.

- **ValidatorAgent** — Ensures the final SQL is executable and semantically correct by executing, repairing failures (≤2 rounds), and validating results match user intent.

## Full Workflow

```
                                   ┌─────────────────────-┐
                                   │   User Question      │
                                   └──────────┬───────────┘
                                              │
                                              v
                    ┌──────────────────────────────────────────────┐
                    │         generateSqlNode: SQLAgent            │◄─────────────┐
                    │         (ReAct Tool-Use Loop)                │              │
                    │                                              │              │
                    │  ┌────────────────────────────────────────┐  │              │
                    │  │  Tool-use loop (max 2 rounds):         │  │              │
                    │  │   • search_value(term)                 │  │              │
                    │  │   • get_distinct_values(table, col)    │  │              │
                    │  │   • get_columns(table)                 │  │              │
                    │  └────────────────────────────────────────┘  │              │
                    │                                              │              │
                    │  Output: SQL + Intent Classification         │              │
                    │  Intents: Clear / Ambiguous / Irrelevant     │              │
                    └───────────────────┬──────────────────────────┘              │
                                        │                                         │
          ┌─────────────────────────────┼──────────────────────────────────┐      │
          │                             │                                  │      │
          v                             v                                  v      │
     Irrelevant                    Ambiguous                             Clear    │
          │                             │                                  │      │
          v                  ┌──────────┴───────────┐                      v      │
     Return NULL             │                      │                  kCandidatesNode
      Query         multiConversational=OFF   multiConversational=ON   ┌──────────────────┐
                             │                      │                  │ Temp 0.7 → Val?  │
                             v                      v                  │  Exit on pass    │
                        Return Hint        ┌─────────────────┐         │ Temp 0.3 → Val?  │
                         Comment           │clarificationNode│         │ Temp 1.0 → Val?  │
                                           │  Ask User for   │         │  ...retry...     │
                                           │  Input, Reframe │         └────────┬─────────┘
                                           │  Question       │                  │
                                           └────────┬────────┘                  v
                                                    │              ┌───────────────────────┐
                                                    │              │    ValidatorAgent     │
                                                    │              │  ┌─────────────────┐  │
                                                    └──────────────►  │  Execute SQL    │  │
                                              (re-runs SQLAgent)   │  │  Repair (≤2x)   │  │
                                                                   │  │  Semantic check │  │
                                                                   │  │  Fix output     │  │
                                                                   │  └─────────────────┘  │
                                                                   └──────────┬────────────┘
                                                                              │
                                                                           Pass?
                                                                        ┌─────┴──────┐
                                                                        │            │
                                                                       Yes           No
                                                                        │            │
                                                                        v            v
                                                                    Return       Retry or
                                                                    Final SQL      Fail
```

---

# 2. Why My Solution Stands Out

- **Clean Code Organization** — clearly separated folders for agents, graph, schemas, utils, and testing. (See [Code Organization](#6-code-organization))

- **Modern LangGraph Workflow** — entire pipeline with a shared state containing conditional edges, not a chain of if-statements.

- **SQLAgent Techniques** — ReAct Tool-Use Loop, Chain-of-Thought Prompting, Dynamic Few-Shot Learning, Schema Grounding. (See [SQLAgent (Generator)](#1-sqlagent-generator))

- **ValidatorAgent** — two-phase execution + semantic review with self-correction loops. (See [ValidatorAgent (Verifier + Fixer)](#2-validatoragent-verifier--fixer))

- **K-Candidate Generation with Temperature Diversity** — Generates candidates at varied temperatures and exits as soon as the first one passes execution and semantic review. Easy and medium queries almost always succeed on the first attempt (temperature 0.7) and cost exactly one generation. Hard queries benefit from temperature diversity and retry resilience when the first attempt fails.

- **Graceful Query Handling** — Handle all sorts of user queries, ambiguous and irrelevant queries are detected and handled without crashing the pipeline. (See [Handling Ambiguous & Irrelevant Queries](#3-handling-ambiguous--irrelevant-queries))

- **Multi-Conversational Mode** — (OPTIONAL) Can be turned on and off to prevent interference with automated testing. Allows interactive clarification for ambiguous queries by pausing to ask the user for details, then reframing their answer into a clean unambiguous question. (See [Enabling Features](#5-enabling-features) for how to enable) 

---


# 3. Handling Ambiguous & Irrelevant Queries

## Ambiguous Query Handling

If `multiConversational` is enabled (see [Enabling Features](#5-enabling-features)), the pipeline detects vague terms and pauses to ask the user a clarification question. The user's answer is fed back to an LLM which **rewrites the original question** into a clean, unambiguous form before re-running SQL generation. See the example below:

```
Enter your question: Show me the best products

🎯 Intent: Ambiguous
🤔 What do you mean by 'best' — the most expensive products,
   highest revenue, or something else?
Your answer: highest revenue

🔄 Reframed question: Show me the products with the highest revenue
                      in the bike store database.

Generated SQL:
   SELECT p.product_name,
          SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS total_revenue
   FROM products p
   JOIN order_items oi ON p.product_id = oi.product_id
   GROUP BY p.product_id, p.product_name
   ORDER BY total_revenue DESC
```

When `multiConversational` is disabled (e.g. automated evaluation), the pipeline exits cleanly with a hint instead of blocking on `input()`:
```
Enter your question: Show me the best products

❓ Query was ambiguous — try being more specific.
   Hint: What do you mean by 'best' — highest revenue, most orders, or something else?

Enter your question: 
```

## Irrelevant Query Detection

Queries that have no connection to a bike store database are identified and skipped before any SQL is generated or validated.

```
Enter your question: Why am I feeling sick in the store?

  Query has no relevance to the bike store database.

Enter your question: 

```

---



# 4. Agent Design + Techniques

This system is built as a **multi-agent architecture** where each agent has a clearly defined responsibility. The design separates generation, validation, and orchestration to improve reliability and correctness.


## 1. SQLAgent (Generator)

**Role:** Converts natural language questions into SQL queries.

**Models:**
- `qwen2.5-coder:14b` — SQL generation. Strong code reasoning and structured JSON output via schema enforcement.
- `llama3.1:8b` — ReAct tool-use loop. Used separately because `qwen2.5-coder` has poor function-calling support; `llama3.1:8b` reliably decides when and how to invoke tools.
- `all-MiniLM-L6-v2` — Sentence embedding for dynamic few-shot retrieval (via `sentence-transformers`).

### Techniques Used:

#### **Chain-of-Thought (CoT) Prompting**  
  Encourages step-by-step reasoning (tables → joins → filters → aggregations) before producing SQL. Follows clear steps in the system prompt. 
```
utils/prompts.py

      def buildSystemPrompt() -> str:

         ...
   
        REASONING PROCESS:
        You must think through each query step-by-step using Chain-of-Thought reasoning:
         
        Step 2: What tables are needed?
        Step 3: What columns should be selected?
        Step 4: Are any JOINs needed?
        Step 5: Are any WHERE filters needed?
        Step 6: Are any aggregations needed (COUNT, SUM, AVG, etc.)?
        Step 7: Is GROUP BY needed?
        Step 8: Is ORDER BY needed?
        Step 9: Is a LIMIT needed?
      
```
**NOTE: Step 1 is a part of the intent clarification written above these steps**, see `src/utils/prompts.py`

#### **Dynamic Few-Shot Learning**
  Embedding model: **`all-MiniLM-L6-v2`** (via `sentence-transformers`) — lightweight, fast, and accurate enough for semantic query matching.

  Injects relevant example queries per question to assist LLM. Uses cosine similarity over sentence embeddings to select the top 5 most relevant examples from a curated bank of 20+ patterns covering basic aggregations, multi-table JOINs, self-joins, subqueries, CTEs, window functions, top-per-group problems, and common pitfalls with explicit counter-examples.
```
src/utils/fewShotExamples.py

FEW_SHOT_EXAMPLES = [
    FewShotExample(
        question="How many products are in each category?",
        sql="SELECT c.category_name, COUNT(p.product_id) FROM categories c LEFT JOIN products p ON c.category_id = p.category_id GROUP BY c.category_name",
        explanation="JOIN with GROUP BY aggregation"
    ),
    FewShotExample(
        question="For each store, show the most expensive product in stock",
        sql="SELECT s.store_name, p.product_name, p.list_price FROM stores s JOIN stocks st ON s.store_id = st.store_id JOIN products p ON st.product_id = p.product_id WHERE (s.store_id, p.list_price) IN (SELECT st2.store_id, MAX(p2.list_price) FROM stocks st2 JOIN products p2 ON st2.product_id = p2.product_id GROUP BY st2.store_id)",
        explanation="Top-1 per group pattern: use subquery to find MAX per group."
    ),
    FewShotExample(
        question="Which staff members manage other staff?",
        sql="SELECT m.first_name, m.last_name, COUNT(s.staff_id) FROM staffs m JOIN staffs s ON m.staff_id = CAST(s.manager_id AS BIGINT) GROUP BY m.staff_id, m.first_name, m.last_name",
        explanation="Self-join hierarchy pattern: alias table twice and join ON manager_id."
    ),
    # ... 20 more patterns
]

```


#### **ReAct Tool-Use Loop (Reasoning + Acting)**
Model: **`llama3.1:8b`** — chosen for its native function-calling support, which makes tool usage reliable and deterministic.

Instead of hoping the LLM remembers every column name and value correctly, the SQLAgent wraps its generation in a **ReAct loop** where the model can reason about the question, decide it needs to verify something, call a tool, get real data back and enrich its information before generating the SQL.

The loop runs up to 2 tool rounds before requiring a final answer. If the LLM decides it doesn't need any tools, it skips straight to SQL generation, so we can reduce overhead for simple queries.

**Three read only database tools are available:**

| Tool | What it does | When the model uses it |
|---|---|---|
| `get_distinct_values(table, column)` | Returns up to 20 distinct values from a column | Verifying exact string casing for WHERE filters (e.g. is it `'Trek'` or `'trek'`?) |
| `search_value(term)` | Fuzzy-searches all VARCHAR columns across all tables | Finding which table/column contains a value the user mentioned |
| `get_columns(table)` | Returns all column names and types for a table | Confirming exact column names before SELECT or WHERE |

```
Example USAGE: User asks "Show me orders with Electra bikes"

ReAct Round 0:
  LLM thinks: "User mentioned 'Electra' — I should verify where this value lives."
  Tool call:  {"action": "tool_call", "tool": "search_value", "term": "Electra"}
  Result:     brands.brand_name: ['Electra']
              products.product_name: ['Electra Townie Original 21D - 2016', ...]

ReAct Round 1:
  LLM thinks: "Electra is a brand. I need to join brands → products → order_items → orders."
  Final answer: SELECT o.order_id, o.order_date, ...
                FROM brands b
                JOIN products p ON b.brand_id = p.brand_id
                JOIN order_items oi ON p.product_id = oi.product_id
                JOIN orders o ON oi.order_id = o.order_id
                WHERE b.brand_name = 'Electra'
```

If all tool rounds complete without the model calling a tool, the agent proceeds directly to the final structured call with a strict Pydantic schema constraint (`format=SQLResult.model_json_schema()`) — so it never crashes.

```
src/agents/tools/tools.py        # Tool implementations (get_distinct_values, search_value, get_columns)
src/agents/tools/toolHelpers.py  # getTools() schema definitions + executeTool() dispatcher
src/agents/SQLAgent.py           # ReAct loop in generate()
src/utils/prompts.py             # System + user prompt builders
```


#### **Schema Grounding**  
  Provides context to the LLM, including the table names and actual sample column data, to reduce hallucinations.

```
utils/prompts.py
   #When calling chat completion we build a prompt that combines Schema Context which includes row examples along with our FewShotExamples.
   def buildUserPrompt(question: str, schemaContext: str, fewShotContext: str) -> str:
```

---

## 2. ValidatorAgent (Verifier + Fixer)

**Role:**  
Ensures that generated SQL is both executable and semantically correct before returning to the user.

**Model: `qwen2.5-coder:14b`** — same model as SQL generation, reused here for execution repair and semantic review since it already has strong code reasoning and schema familiarity from the generation phase.

### Techniques Used

#### Execution and Semantic Review
   Unlike other validator agents, this agent combines TWO important aspects, execution and semantics. The agent is given context to perform both reviews as accurately as possible. 

#### Self-Correction Loops (≤ 2 Rounds)
   If execution fails, the agent performs 2 repair attempts. If execution works, the agent will obtain sample rows, the user's original query and perform a semantic review. If the agent determines that the SQL results do not match the user's query, it will try to fix it 2 times to match the user's request. 


---

# 5. Enabling Multiconversational Feature

## Multi-Conversational Mode

By default, ambiguous queries return a hint comment (`-- AMBIGUOUS_QUERY: ...`) so the pipeline never blocks on `input()` during automated evaluations. To enable the interactive clarification loop, set the flag in `agent.py`:

```python
# agent.py — QueryWriter.__init__
self.multi_conversational_enabled = True   # ask user to clarify ambiguous queries
```

When enabled, the pipeline will pause on ambiguous queries, ask a targeted question, reframe the answer into a clean unambiguous question using an LLM call, and re-run generation.

**Must be `False` during automated evaluation** to avoid hanging on `input()`.

---

# 6. Code Organization

Organized to be readable and scalable. I use Pydantic schemas to reduce errors and provide the LLM with a consistent output format. The LangGraph workflow, agents, utils (with helpers and prompts) and tests I used are all organized in their own respective folders.

```
carleton_competition_winter_2026/
│
├── agent.py                        # Competition interface (QueryWriter)
├── main.py                         # Interactive CLI entry point
│
└── src/
    ├── agents/
    │   ├── SQLAgent.py             # SQL generation with CoT + Few-Shot + ReAct tool-use loop
    │   ├── ValidatorAgent.py       # Execution + semantic review with self-correction
    │   └── tools/
    │       ├── tools.py            # get_distinct_values, search_value, get_columns
    │       └── toolHelpers.py      # getTools() definitions + executeTool() to call tool
    │
    ├── graph/
    │   ├── GraphWorkflow.py        # LangGraph workflow definition & conditional edges
    │   ├── Nodes.py                # Node functions (generateSqlNode, kCandidatesNode, ...)
    │   ├── State.py                # Typed shared state schema
    |   |
    │   └── visualization/
    │       ├── visualize_graph.py  # Not submission relevant — visualize graph for fun
    │       └── graph.png           # Generated LangGraph workflow visualization
    │
    ├── schemas/                    # Pydantic output schemas for SQLAgent + ValidatorAgent
    │
    ├── utils/
    │   ├── helpers.py              # loadSchema, buildSchemaContext, executeSQL
    │   ├── prompts.py              # System + user prompt builders
    │   ├── fewShotExamples.py      # Bank of few-shot examples for SQLAgent
    │   └── constants.py            # Constants
    │
    └── testing/                    # I used an automated script to help improve my submission
```


---

# 7. Challenges Faced

I went through lots of trial and error to solve this problem. Originally, I had 3 agents: a QuestionDecomposerAgent, a SchemaExpertAgent, and an SQLGeneration Agent. Although this type of architecture may seem advanced, it was inaccurate and error-prone. After some research, I realized that a multi-agent workflow of that format is not useful for this problem. A degree of error is carried over from each agent, and if the first agent misunderstood the question even slightly, the whole workflow is ruined. I also played around with a RAG (Retrieval Augmented Generation) setup to add more context, but for this dataset, the schema is small enough to fit directly in the prompt. RAG added extra complexity, latency and didn’t help enough to justify it.

After that, I pivoted to my more reliable setup one "MASTER" SQL agent that focuses on understanding the question and generating SQL supported by a separate ValidatorAgent that executes the query, fixes obvious failures, and semantic checks that the output actually matches the question. This approach produced much more accurate results and let me focus on tightening the system’s reliability (instead of debugging a long chain of agents).

---

# 8. About Me

Hi! I’m Ansh Kakkar, a 3rd-year Computer Science student at Carleton University. I love building things, joining hackathons and learn by making personal projects in my free time.

- Portfolio (RAG Chatbot): https://anshkakkar.dev
- GitHub (Check out my projects): https://github.com/anshk8
- LinkedIn (Let's Connect): https://www.linkedin.com/in/ansh-kakkar

---
