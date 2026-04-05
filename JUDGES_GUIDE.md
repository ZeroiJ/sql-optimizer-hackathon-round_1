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
{"query": "CREATE INDEX idx_city ON customers(city);"}

--- Attempt 1/5 ---
  Reward: 0.2000
  Current Score: 0.2000
  Correctness: 0.0
  Efficiency: 0.0
  is_valid_sql: 1.0
  Done: False
```

**What happened:** Llama-3 recognized that an index might help performance and created one — but never actually fixed the broken SELECT query. The grader correctly:

1. **Awarded `is_valid_sql = 1.0`** — `CREATE INDEX` is syntactically valid SQL
2. **Awarded `correctness = 0.0`** — the broken query's result set (with wrong column names) does NOT match the expected query's result set (semantic equivalence failed)
3. **Awarded `efficiency = 0.0`** — no improvement to the query plan of the broken query
4. **Final score: 0.20** — `0.5 * 0.0 + 0.3 * 0.0 + 0.2 * 1.0 = 0.20`, well below the 0.95 threshold

**Why this matters:** The environment doesn't just check if the submission is syntactically valid SQL. A naive grader would see `is_valid_sql = 1.0` and award partial credit. Our grader requires **semantic equivalence** — the agent's query must produce the exact same rows as the reference query. An agent that submits valid but irrelevant SQL (like a lone `CREATE INDEX`) scores 0.20. An agent that fixes the column names but misses the logic scores partial credit. An agent that produces the correct result set with a better plan scores 0.95+. This is **real RL signal**, not a binary pass/fail.

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
