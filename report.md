
# MindBridge × Carleton SQL Query Writer Agent (2026)
**Author:** Ansh Kakkar (Student#: 101298368) 
**Due Date:** March 13, 2026  

## Table of Contents

1. [Architecture Overview](#1-architecture-overview-inside-langgraph-workflow)
2. [Why My Solution Stands Out](#2-why-my-solution-stands-out)
3. [How to Toggle Features](#3-enabling-features)
4. [Agent Designs + Techniques](#4-agent-design--techniques)
5. [Code Organization](#5-code-organization)
6. [Challenges Faced](#6-challenges-faced)
7. [About Me](#7-about-me)

---

# 1. Architecture Overview (Inside LangGraph Workflow)

My submission uses an SQL Generation Agent powered by a **ReAct (Reasoning + Acting) tool-use loop**, followed by K-Candidate generation with a ValidatorAgent for execution and semantic review. Before committing to final SQL, the model can call lightweight database tools to look up real values and verify schema details — meaning the generated query is grounded in actual data, not just the LLM's memory.

Every query passes through `generateSqlNode` first for intent classification (Clear / Ambiguous / Irrelevant). Clear queries are then routed to `kCandidatesNode`, which generates candidates at varied temperatures and exits as soon as the first one passes execution and semantic review. Easy and medium queries almost always succeed on the first attempt (temperature 0.7) and cost exactly one generation. Hard queries benefit from temperature diversity and retry resilience when the first attempt fails.

```
                         ┌─────────────────────┐
                         │     User Question   │
                         └──────────┬──────────┘
                                    │
                                    v
                    ┌──────────────────────────────────────┐
                    │   SQLAgent  (ReAct Tool-Use Loop)    │ ◄── (clarify loop-back)
                    │   generateSqlNode                    │
                    │                                      │
                    │   ┌──────────────────────────────┐   │
                    │   │ LLM decides: need a tool?    │   │
                    │   │  YES → call tool, get result │   │
                    │   │         loop back (max 2x)   │   │
                    │   │  NO  → produce final answer  │   │
                    │   └──────────────────────────────┘   │
                    │                                      │
                    │   Tools:                             │
                    │    • get_distinct_values(table, col) │
                    │    • search_value(term)              │
                    │    • get_columns(table)              │
                    │                                      │
                    │   Intent: Clear / Ambiguous /        │
                    │           Irrelevant                 │
                    └──────────────────┬───────────────────┘
                                       │
              ┌──────────┬─────────────┼──────────────────────────┐
              │          │             │                           │
           Irrel.    Ambig.        Ambig.                       Clear
                     (mc=T)        (mc=F)
              │          │             │                           │
            exit        ask          exit hint              kCandidatesNode
                    clarify                            temps: [0.7, 0.3, 1.0, 0.5, ...]
                      Node                             validate each, exit early on pass
              │       │ (loop back)                               │
              v       v                                           v
             END    SQLAgent                                  Final SQL
```

---

# 2. Why My Solution Stands Out

### Clean Code Organization
The project is structured into clearly separated folders — `agents/`, `graph/`, `schemas/`, `utils/`, `db/`, and `testing/` making the codebase easy to extend.

### Modern Agentic Framework with LangGraph
Instead of a tangled chain of `if` statements, the entire workflow is modelled as a **LangGraph state machine** with typed shared state (`graph/State.py`) and conditional edges. This makes the workflow and adding new features simpler. 

### Innovative Features
- **ReAct Tool-Use Agent** — the SQLAgent doesn't just guess at column values and table names. It runs a ReAct (Reasoning + Acting) loop where the LLM can call real database tools — like looking up distinct brand names or searching for where a value lives — before writing the SQL. This means the generated query uses exact casing, correct column names, and verified filter values instead of relying on the model's memory.
- **K-Candidate Generation with Temperature Diversity** — every query goes through `kCandidatesNode`, which generates candidates at a spread of temperatures (`[0.7, 0.3, 1.0, 0.5, 0.9, 1.2]`) and exits as soon as one passes execution and semantic review. Easy and medium queries cost exactly one generation (the default 0.7 pass almost always succeeds), while hard queries automatically benefit from diversity and retry without any manual configuration.
- **Multi-Conversational Support** — ambiguous or unclear questions are handled gracefully through a conversational clarification loop rather than silently returning a wrong query.

### Ambiguous Query Handling

When `multiConversational` is enabled, the pipeline detects vague terms (e.g. *best*, *popular*, *worst*) and pauses to ask the user a targeted clarification question. The user's answer is fed back to an LLM which **rewrites the original question** into a clean, unambiguous form before re-running SQL generation — so the model never receives a confusing appended string like `"best products (highest revenue)"`.

```
Enter your question: Show me the best products

🎯 Intent: Ambiguous
🤔 What do you mean by 'best' — the most expensive products,
   highest revenue, or something else?
Your answer: highest revenue

🔄 Reframed question: Show me the products with the highest revenue
                      in the bike store database.

Generating...
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
❓ Query was ambiguous — try being more specific.
   Hint: What do you mean by 'best' — highest revenue, most orders, or something else?
```

### Irrelevant Query Detection

Queries that have no connection to a bike store database are identified and skipped before any SQL is generated or validated. This prevents wasted LLM calls and avoids returning confusing empty results.

```
Enter your question: Why am I feeling sick in the store?

🎯 Intent: Irrelevant
❌ Query has no relevance to the bike store database.

Generated SQL:
-- IRRELEVANT_QUERY: This question cannot be answered
                     from the bike store database.
```

### Proven Prompting Techniques
Chain-of-Thought (CoT) reasoning, embedding-based Dynamic Few-Shot retrieval, schema grounding with live sample rows, ReAct tool-use for real data verification, and Self-Correction loops are all layered together to push SQL accuracy as high as possible.

---

# 3. Enabling Features

## Multi-Conversational Mode
By default, ambiguous queries return a hint comment (`-- AMBIGUOUS_QUERY: ...`) so the pipeline never blocks on `input()` during automated evaluation. To enable the interactive clarification loop, set the flag in `agent.py`:

```python
# agent.py — QueryWriter.__init__
self.multi_conversational_enabled = True   # ask user to clarify ambiguous queries
```

When enabled, the pipeline will pause on ambiguous queries, ask a targeted question, reframe the answer into a clean unambiguous question using an LLM call, and re-run generation.

**Must be `False` during automated evaluation** to avoid hanging on `input()`.




# 4. Agent Design + Techniques

This system is built as a **multi-agent architecture** where each agent has a clearly defined responsibility. The design separates generation, validation, and orchestration to improve reliability and correctness.


## 1. SQLAgent (Generator)

**Role:** Converts natural language questions into SQL queries.

### Techniques Used:

#### **ReAct Tool-Use Loop (Reasoning + Acting)**
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
  Injects relevant example queries per question to assist LLM. Uses embedding similarity to select the top 3 most relevant examples from a query bank of different example prompts.
```
agents/SQLAgent.py

      #Different Examples included in the agent
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

### Techniques Used

#### Execution and Semantic Review
   Unlike other validator agents, this agent combines TWO important aspects, execution and semantics. The agent is given context to perform both reviews as accurately as possible. 

#### Self-Correction Loops (≤ 2 Rounds)
   If execution fails, the agent performs 2 repair attempts. If execution works, the agent will obtain sample rows, the user's original query and perform a semantic review. If the agent determines that the SQL results do not match the user's query, it will try to fix it 2 times to match the user's request. 


---

## 5. Code Organization

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
    │   └── State.py                # Typed shared state schema
    │
    ├── schemas/                    # Pydantic output schemas for SQLAgent + ValidatorAgent
    │
    ├── utils/
    │   ├── helpers.py              # loadSchema, buildSchemaContext, executeSQL
    │   └── prompts.py              # System + user prompt builders
    │
    └── testing/                    # Test suite and saved test results
```


---

## 6. Challenges Faced

I went through lots of trial and error to solve this problem. Originally, I had 3 agents: a QuestionDecomposerAgent, a SchemaExpertAgent, and an SQLGeneration Agent. Although this type of architecture may seem advanced, it was inaccurate and error-prone. After some research, I realized that a multi-agent workflow of that format is not useful for this problem. A degree of error is carried over from each agent, and if the first agent misunderstood the question even slightly, the whole workflow is ruined. I also played around with a RAG (Retrieval Augmented Generation) setup to add more context, but for this dataset, the schema is small enough to fit directly in the prompt. RAG added extra complexity, latency and didn’t help enough to justify it.

After that, I pivoted to my more reliable setup one "MASTER" SQL agent that focuses on understanding the question and generating SQL supported by a separate ValidatorAgent that executes the query, fixes obvious failures, and semantic checks that the output actually matches the question. This approach produced much more accurate results and let me focus on tightening the system’s reliability (instead of debugging a long chain of agents).

---

## 7. About Me

Hi! I’m Ansh Kakkar, a 3rd-year Computer Science student at Carleton University. I love building things, joining hackathons and learn by making personal projects in my free time.

- Portfolio (RAG Chatbot): https://anshkakkar.dev
- GitHub (Check out my projects): https://github.com/anshk8
- LinkedIn (Let's Connect): https://www.linkedin.com/in/ansh-kakkar

---
