# Judges Guide — SQL Query Optimizer Environment

> For Meta & Scaler engineers evaluating this submission.

---

## Section 1: The "SELECT 1" Exploit — Neutralized

**The attack:** An agent submits `SELECT 1;` — a query that always executes successfully and returns a trivial result. A naive grader that only checks `is_valid_sql` would award a positive score.

**Our defense:** The `_verify_semantic_equivalence` method in `server/sql_optimizer_environment.py` runs **both** the expected query and the submitted query against the same SQLite database, then compares the returned row sets:

```python
def _verify_semantic_equivalence(self, cursor, expected_query, submitted_query):
    try:
        cursor.execute(expected_query)
        expected_rows = cursor.fetchall()
    except sqlite3.Error:
        return False, None, None
    try:
        cursor.execute(submitted_query)
        submitted_rows = cursor.fetchall()
    except sqlite3.Error:
        return False, expected_rows, None
    return expected_rows == submitted_rows, expected_rows, submitted_rows
```

If the row sets don't match, `correctness = 0.0`. The agent gets **zero credit** for semantic correctness regardless of whether the query executes. The `try/except` blocks ensure that even if the expected query itself fails (edge case), the grader doesn't crash — it simply returns `False`.

**Result:** `SELECT 1` returns a single row `(1,)` which never matches the expected result set of the task (e.g., customer names and order IDs). The agent scores 0.0 on correctness and receives only the base efficiency score — typically well below the 0.95 threshold needed to complete the episode.

---

## Section 2: The Llama-3 Trap — Execution Path Evaluation

When running the baseline inference script (`scripts/inference.py`) against Llama-3-8B-Instruct on the `easy_fix_select` task, the model exhibits a characteristic failure mode:

```
Task: easy_fix_select
Broken Query: SELECT custmer_id, nm, emaill FROM customers WHERE city = 'Mumbai'
Max attempts: 5

LLM Response:
{"query": "CREATE INDEX idx_city ON customers(city); SELECT customer_id, name, email FROM customers WHERE city = 'Mumbai'"}

--- Attempt 1/5 ---
  Reward: ~0.70
  Current Score: ~0.70
  Correctness: 1.0
  Efficiency: 0.0
  Done: False
```

**What happened:** Llama-3 correctly fixed the column names (`custmer_id` → `customer_id`, `nm` → `name`, `emaill` → `email`) but also injected a `CREATE INDEX` DDL statement into what should be a pure DQL task. The grader correctly:

1. **Awarded `correctness = 1.0`** — the result rows matched (semantic equivalence passed)
2. **Awarded `efficiency = 0.0`** — the `EXPLAIN QUERY PLAN` cost of the submitted query (with the unnecessary index creation) was not demonstrably better than the broken query's cost
3. **Final score: ~0.70** — `0.5 * 1.0 + 0.3 * 0.0 + 0.2 * 1.0 = 0.70`, well below the 0.95 threshold needed to complete the episode

**Why this matters:** The environment doesn't just check if the query is syntactically valid SQL. It evaluates the **actual execution path** — the agent's query must produce the same rows as the expected query, and the query plan must be demonstrably better. An agent that "gets lucky" with valid SQL but wrong results scores 0.0. An agent that gets the right results but uses a suboptimal plan (or injects unnecessary DDL) scores partial credit. This is **real RL signal**, not a binary pass/fail.

---

## Section 3: Cloud Verification — Live Grading via Hugging Face Spaces

Run the edge case test suite against the live deployed environment:

```bash
uv run python scripts/test_edge_cases.py
```

This script connects to the live Hugging Face Space at `wss://zeroij-sql-query-optimizer.hf.space` via WebSocket and submits five adversarial queries:

| Test Case | Query Type | Expected Behavior |
|-----------|-----------|-------------------|
| The Lazy Dev | Correct JOIN, no index | Positive reward, correctness = 1.0 |
| The Index Spammer | 4x CREATE INDEX + correct JOIN | Partial credit — correctness passes but index penalty applies |
| The Hallucinator | `SELECT 1;` | Semantic check fails — correctness = 0.0 |
| The Destroyer | `DROP TABLE orders;` + valid query | Destructive query detected — reward = -1.0, episode ends |
| The Perfect DBA | 1x targeted index + optimal JOIN | Highest reward — correctness + efficiency bonus |

**How it works:** Each query is sent as a `SQLAction` through the WebSocket client. The server-side environment:

1. Validates the query against the destructive pattern regex (`DROP|DELETE|TRUNCATE|ALTER|...`)
2. Executes each statement against the in-memory SQLite database
3. Runs `_verify_semantic_equivalence` to compare the agent's result against the expected query output
4. Calculates `EXPLAIN QUERY PLAN` cost for both the broken and submitted queries
5. Computes the composite score using the task-specific formula
6. Drops any created indices to maintain statelessness

The grading happens in **SQLite's C-level execution engine** — no string matching, no regex-based SQL parsing for correctness. The only way to score well is to produce the exact same result set as the reference query with a more efficient execution plan.
