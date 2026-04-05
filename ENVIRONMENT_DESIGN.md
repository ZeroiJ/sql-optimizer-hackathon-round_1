# Environment Design — SQL Query Optimizer
> Internal doc for the team. Read this before writing a single line of code.
> If something conflicts with what you're building, raise it immediately.

---

## Overview

We are building an OpenEnv-compliant environment where an AI agent is given a SQL query that is either broken, incorrect, or inefficient — and must submit a fixed/optimized version.

The environment runs on **SQLite** (no external DB server, works anywhere, Docker-friendly).

---

## Database Schema

We use a single e-commerce style database. Everyone on the team must use this exact schema — no deviations.

```sql
-- Customers table
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    city TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER DEFAULT 0
);

-- Orders table
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- Order items table
CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- Reviews table
CREATE TABLE reviews (
    review_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    review_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
```

**Seed data:** ~100 customers, ~50 products, ~300 orders, ~600 order_items, ~200 reviews.
Seed script lives at `env/seed.py`. Must be deterministic (fixed random seed).

---

## OpenEnv API Contract

This is the interface everyone must agree on. Person 1 implements this. Person 2 and 3 consume it.

### Pydantic Models

```python
from pydantic import BaseModel
from typing import Optional, Dict, Any

class Observation(BaseModel):
    task_id: str                    # Which task is active e.g. "easy_01"
    schema_description: str         # Human-readable schema summary
    broken_query: str               # The query the agent needs to fix
    error_message: Optional[str]    # Error if last submission failed, else None
    current_score: float            # Running score for this episode (0.0 - 1.0)
    attempts: int                   # How many attempts agent has made
    max_attempts: int               # Max attempts allowed for this task

class Action(BaseModel):
    query: str                      # The SQL query the agent submits

class Reward(BaseModel):
    value: float                    # Reward for this step (-1.0 to 1.0)
    correctness: float              # Did it return correct rows? (0.0 - 1.0)
    efficiency: float               # Is the query plan better? (0.0 - 1.0)
    is_valid_sql: bool              # Did it even parse/execute?
    done: bool                      # Is the episode over?
    info: Dict[str, Any]            # Extra debug info
```

### Methods

```python
class SQLOptimizerEnv:

    def reset(self, task_id: str = None) -> Observation:
        """
        Resets the environment.
        - Reloads fresh SQLite DB from seed
        - Picks a task (random if task_id is None)
        - Returns initial Observation
        - attempts counter resets to 0
        """

    def step(self, action: Action) -> tuple[Observation, Reward, bool, dict]:
        """
        Agent submits a query.
        - Executes the query against SQLite
        - Runs the grader for the current task
        - Returns (new_observation, reward, done, info)
        - done=True if: max_attempts reached OR score >= 0.95
        - Increments attempts counter
        """

    def state(self) -> dict:
        """
        Returns current raw state of the environment.
        - Current task_id
        - Current attempts
        - Current score
        - Whether episode is done
        """
```

### Episode Flow

```
reset(task_id) 
    → returns Observation (broken query, schema, attempts=0)
    
step(Action(query="SELECT ..."))
    → grader runs
    → returns (Observation, Reward, done, info)
    → if done=True, episode is over
    
# Agent can keep stepping until done=True
# Max attempts per task: Easy=5, Medium=7, Hard=10
```

---

## The 3 Tasks

### Task 1 — Easy: Fix the Broken SELECT
**Task ID:** `easy_fix_select`
**Max attempts:** 5

**Scenario:** A query has a wrong column name and a missing condition.

**Broken query given to agent:**
```sql
SELECT custmer_id, nm, emaill
FROM customers
WHERE city = 'Mumbai'
```

**Expected fix:**
```sql
SELECT customer_id, name, email
FROM customers
WHERE city = 'Mumbai'
```

**Expected output:** All customers from Mumbai with correct columns.

**Grader logic:**
- `is_valid_sql`: Does it execute without error? (binary)
- `correctness`: Does result match expected rows exactly? (0.0 or 1.0)
- `partial_credit`: Correct columns but wrong/missing WHERE → 0.4. Valid SQL but wrong result → 0.2.
- **Final score:** `0.5 * correctness + 0.3 * column_match + 0.2 * is_valid_sql`

---

### Task 2 — Medium: Rewrite the Slow JOIN
**Task ID:** `medium_slow_join`
**Max attempts:** 7

**Scenario:** A query uses a cartesian product (missing JOIN condition) causing massive result explosion.

**Broken query given to agent:**
```sql
SELECT customers.name, orders.order_id, orders.status
FROM customers, orders
WHERE orders.status = 'completed'
```

**Expected fix:**
```sql
SELECT customers.name, orders.order_id, orders.status
FROM customers
JOIN orders ON customers.customer_id = orders.customer_id
WHERE orders.status = 'completed'
```

**Expected output:** Only completed orders matched to their correct customer.

**Grader logic:**
- `is_valid_sql`: Executes without error?
- `correctness`: Result rows match expected output exactly? (0.0 or 1.0)
- `efficiency`: Does query plan use a JOIN instead of cartesian product? Check via `EXPLAIN QUERY PLAN`
- `partial_credit`: Correct result but cartesian product still used → 0.5 (correct but not optimized)
- **Final score:** `0.5 * correctness + 0.3 * efficiency + 0.2 * is_valid_sql`

---

### Task 3 — Hard: Optimize with CTE/Window Function
**Task ID:** `hard_subquery_optimize`
**Max attempts:** 10

**Scenario:** A deeply nested subquery that is correct but extremely slow. Agent must rewrite using CTE or window functions.

**Broken query given to agent:**
```sql
SELECT customer_id, name,
    (SELECT COUNT(*) FROM orders WHERE orders.customer_id = customers.customer_id) as order_count,
    (SELECT SUM(unit_price * quantity) FROM order_items 
     JOIN orders ON order_items.order_id = orders.order_id 
     WHERE orders.customer_id = customers.customer_id) as total_spent
FROM customers
WHERE (SELECT COUNT(*) FROM orders WHERE orders.customer_id = customers.customer_id) > 2
```

**Expected fix (one valid approach):**
```sql
WITH customer_stats AS (
    SELECT 
        o.customer_id,
        COUNT(o.order_id) as order_count,
        SUM(oi.unit_price * oi.quantity) as total_spent
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    GROUP BY o.customer_id
)
SELECT c.customer_id, c.name, cs.order_count, cs.total_spent
FROM customers c
JOIN customer_stats cs ON c.customer_id = cs.customer_id
WHERE cs.order_count > 2
```

**Grader logic:**
- `is_valid_sql`: Executes without error?
- `correctness`: Result matches expected rows and values? (0.0 or 1.0)
- `efficiency`: Does `EXPLAIN QUERY PLAN` show fewer scans than original? Score 0.0-1.0 based on scan reduction ratio.
- `uses_cte_or_window`: Bonus — does the query use WITH or window functions? +0.1 bonus
- **Final score:** `0.4 * correctness + 0.4 * efficiency + 0.1 * is_valid_sql + 0.1 * uses_cte_or_window` (capped at 1.0)

---

## Reward Function Design

### Step-level reward (returned every step)

```python
def compute_reward(correctness, efficiency, is_valid_sql, attempts, max_attempts) -> float:
    if not is_valid_sql:
        return -0.1                          # Penalty for broken SQL

    base = (0.5 * correctness) + (0.3 * efficiency) + (0.2 * float(is_valid_sql))

    # Partial progress bonus — reward improvement over previous attempt
    improvement_bonus = max(0, base - previous_score) * 0.2

    # Efficiency bonus for solving early
    attempt_ratio = attempts / max_attempts
    speed_bonus = 0.1 * (1 - attempt_ratio) if correctness == 1.0 else 0

    return min(1.0, base + improvement_bonus + speed_bonus)
```

### Penalties
- Invalid SQL (parse error): `-0.1`
- Destructive query (DROP, DELETE, TRUNCATE, ALTER): `-1.0` and episode ends immediately
- Exceeding max attempts: episode ends, final score is whatever was achieved

### Episode end conditions
- Agent scores `>= 0.95` → done, success
- Agent exceeds `max_attempts` → done, partial score kept
- Agent submits destructive query → done, score = 0.0

---

## openenv.yaml Structure

```yaml
name: sql-query-optimizer
version: 1.0.0
description: >
  An OpenEnv environment where an AI agent must fix and optimize
  SQL queries against a real SQLite e-commerce database.
author: Team [your names]
tags:
  - sql
  - database
  - optimization
  - real-world

observation_space:
  type: object
  fields:
    task_id: string
    schema_description: string
    broken_query: string
    error_message: string | null
    current_score: float
    attempts: integer
    max_attempts: integer

action_space:
  type: object
  fields:
    query: string

reward_range: [-1.0, 1.0]

tasks:
  - id: easy_fix_select
    difficulty: easy
    max_attempts: 5
  - id: medium_slow_join
    difficulty: medium
    max_attempts: 7
  - id: hard_subquery_optimize
    difficulty: hard
    max_attempts: 10

entry_point: env.sql_optimizer:SQLOptimizerEnv
```

---

## Project Folder Structure

```
sql-optimizer-env/
├── env/
│   ├── __init__.py
│   ├── sql_optimizer.py      # Core env: step(), reset(), state()
│   ├── models.py             # Pydantic models: Observation, Action, Reward
│   ├── database.py           # SQLite connection + schema init
│   ├── seed.py               # Deterministic seed data generator
│   └── tasks/
│       ├── __init__.py
│       ├── easy_fix_select.py
│       ├── medium_slow_join.py
│       └── hard_subquery_optimize.py
├── graders/
│   ├── __init__.py
│   ├── base_grader.py        # Abstract grader class
│   ├── easy_grader.py
│   ├── medium_grader.py
│   └── hard_grader.py
├── baseline/
│   └── run_baseline.py       # OpenAI API baseline agent script
├── tests/
│   ├── test_env.py
│   ├── test_graders.py
│   └── test_baseline.py
├── openenv.yaml
├── Dockerfile
├── requirements.txt
├── README.md
├── HACKATHON_RULES.md
├── ENVIRONMENT_DESIGN.md     # This file
└── GRADER_SPEC.md
```

---

## Person Responsibilities (Code Ownership)

| Person | Files They Own |
|--------|---------------|
| **Person 1 (Sujal)** | `env/sql_optimizer.py`, `env/models.py`, `env/database.py`, `env/seed.py`, `openenv.yaml` |
| **Person 2** | `env/tasks/*`, `graders/*`, reward function inside `sql_optimizer.py` |
| **Person 3** | `baseline/run_baseline.py`, `Dockerfile`, `requirements.txt`, `README.md` |

---

## Critical Agreements (Everyone Must Follow)

1. **Never modify the schema** after Day 1. If you need a change, tell everyone first.
2. **Seed data is fixed** — `seed.py` uses `random.seed(42)`. Do not change this.
3. **Graders must be deterministic** — same query in = same score out, always.
4. **No external API calls** inside the env itself — SQLite only, no network.
5. **Destructive queries must be caught** before execution — check for DROP/DELETE/ALTER before running.
6. **All models use Pydantic** — no raw dicts being passed around between modules.
7. **Test your piece locally** with `docker build . && docker run .` before saying it's done.
