
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

My submission uses an SQL Generation Agent with various techniques, followed by a Validator Agent for execution and semantic review (For more details, see the Agent section). 
Additionally, my submission includes a toggleable feature to generate K Candidate Queries for Hard Level problems. This uses a chat-completion endpoint with a diverse range of temperatures to produce different results, ranking each for the best (and hopefully correct) output.

Every query — regardless of flags — passes through `generateSqlNode` first. This ensures intent classification (Clear / Ambiguous / Irrelevant) always runs before any expensive validation or K-candidate generation. Only a **confirmed Clear + Hard** query is routed to `kCandidatesNode`; everything else takes the fast path or exits early.

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
                               └──────┬───────┘
                                      │ (always)
                                      v
                          ┌──────────────────────┐
                          │   SQLAgent           │ ◄─── (clarify loop-back)
                          │   generateSqlNode    │
                          │   Intent: Clear /    │
                          │   Ambiguous /        │
                          │   Irrelevant         │
                          └────────┬─────────────┘
                                   │
              ┌──────────┬─────────┼──────────────┬──────────────────┐
              │          │         │               │                  │
           Irrel.    Ambig.    Ambig.          Clear             Clear+Hard
                     (mc=T)    (mc=F)                            +kEnabled
              │          │         │               │                  │
            exit        ask      exit hint    ValidatorAgent     kCandidatesNode
                    clarify                   execute+fix         K candidates,
                      Node                   semantic review      score & pick
              │       │ (loop back)                │                  │
              v       v                            v                  v
             END    SQLAgent                   Final SQL          Final SQL
```

---

# 2. Why My Solution Stands Out

### Clean Code Organization
The project is structured into clearly separated folders — `agents/`, `graph/`, `schemas/`, `utils/`, `db/`, and `testing/` making the codebase easy to extend.

### Modern Agentic Framework with LangGraph
Instead of a tangled chain of `if` statements, the entire workflow is modelled as a **LangGraph state machine** with typed shared state (`graph/State.py`) and conditional edges. This makes the workflow and adding new features simpler. 

### Innovative Features
- **K-Candidate Generation with Temperature Diversity** — for hard queries the system generates K SQL candidates at varying temperatures, validates each, and selects the best-scoring result, significantly increasing accuracy on complex multi-join problems.
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
Chain-of-Thought (CoT) reasoning, embedding-based Dynamic Few-Shot retrieval, schema grounding with live sample rows and Self-Correction loops are all layered together to push SQL accuracy as high as possible.

---

# 3. Enabling Features

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




# 4. Agent Design + Techniques

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

### 3. DifficultyRankerAgent (Optional – Enabled with K-Candidate Generation)

**Role:** Classifies queries as easy, medium, or hard.

The main goal of the system is high SQL accuracy without unnecessary LLM calls. During testing, I noticed that harder user queries involving multiple JOINs, filters, and aggregations are more likely to produce incorrect SQL. Since my architecture already performs very well on easy-to-medium queries, generating K candidate queries for all questions would be redundant. The DifficultyRankerAgent identifies only hard queries and routes them through K-candidate generation, making the system more efficient and allocating extra reasoning power only where it actually improves accuracy.

---

## 5. Code Organization

Organized to be readable and scalable. I use Pydantic schemas to reduce errors and provide the LLM with a consistent output format. The LangGraph workflow, agents, utils (with helpers and prompts) and tests I used are all organized in their own respective folders.

```
carleton_competition_winter_2026/
│
-------
├── agents/                         # Contains all agent files
│
├── graph/
│   ├── GraphWorkflow.py            # LangGraph workflow definition & conditional edges
│   ├── Nodes.py                    # Node functions invoked by the graph
│   └── State.py                    # Typed shared state schema
│
├── schemas/                        # Pydantic output schemas for each agent
│
├── utils/
│   ├── helpers.py                  # Shared utilities used by agents
│   └── prompts.py                  # System + user prompt builders for agents
│
│
└── testing/                        # Tests and saved test results I used to improve my solution
```


---

## 6. Challenges Faced

I went through lots of trial and error to solve this problem. Originally, I had 3 agents: a QuestionDecomposerAgent, a SchemaExpertAgent, and an SQLGeneration Agent. Although this type of architecture may seem advanced, it was inaccurate and error-prone. After some research, I realized that a multi-agent workflow of that format is not useful for this problem. A degree of error is carried over from each agent, and if the first agent misunderstood the question even slightly, the whole workflow is ruined. I also played around with a RAG (Retrieval Augmented Generation) setup to add more context, but for this dataset, the schema is small enough to fit directly in the prompt. RAG added extra complexity, latency and didn’t help enough to justify it.

After that, I pivoted to my more reliable setup: one “SQL mastermind” agent that focuses on understanding the question and generating SQL with the schema and a few relevant examples in context, and a separate ValidatorAgent that executes the query, fixes obvious failures, and sanity-checks that the output actually matches the question. This approach produced much more accurate results and let me focus on tightening the system’s reliability (instead of debugging a long chain of agents).

---

## 7. About Me

Hi! I’m Ansh Kakkar, a 3rd-year Computer Science student at Carleton University. I love building things, joining hackathons and learn by making personal projects in my free time.

- Portfolio (RAG Chatbot): https://anshkakkar.dev
- GitHub (Check out my projects): https://github.com/anshk8
- LinkedIn (Let's Connect): https://www.linkedin.com/in/ansh-kakkar

---
