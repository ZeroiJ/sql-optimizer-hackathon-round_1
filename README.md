---
title: SQL Query Optimizer
emoji: 🗄️
colorFrom: blue
colorTo: indigo
sdk: gradio
python_version: 3.10
pinned: false
tags:
  - openenv
  - reinforcement-learning
---

# SQL Query Optimizer Environment

**Meta PyTorch OpenEnv Hackathon**

> **📜 For Judges:** See [JUDGES_GUIDE.md](./JUDGES_GUIDE.md) for detailed grading mechanics, anti-hallucination strategies, and cloud verification steps.

A Reinforcement Learning environment that trains AI agents to fix and optimize SQL queries — simulating a real-world Database Administration (DBA) task on a SQLite e-commerce database.

---

## Overview

This environment presents an AI agent with broken, incorrect, or inefficient SQL queries against a real SQLite database. The agent must submit a fixed/optimized version. The environment grades submissions using a **two-stage anti-hallucination engine**:

1. **Semantic Equivalence Check** — executes both queries and compares results. If the data does not match exactly, the Semantic Grader accurately sets Correctness to 0.0, leaving the agent with only a minor syntax reward (e.g., 0.24).
2. **EXPLAIN QUERY PLAN Heuristic** — analyzes the SQLite execution tree, penalizing full table scans (`SCAN` = +100), temporary B-trees (`USE TEMP B-TREE` = +50), and correlated subqueries (`CORRELATED SCALAR SUBQUERY` = +150), while rewarding efficient index usage (`SEARCH` = +10, `COVERING INDEX` = -20).

---

## The 3 Tasks

| Task | Difficulty | Description | Max Attempts |
|------|-----------|-------------|-------------|
| **easy_fix_select** | Easy | Fix wrong column names (`custmer_id` -> `customer_id`, `nm` -> `name`, `emaill` -> `email`) | 5 |
| **medium_slow_join** | Medium | Rewrite a cartesian product (missing JOIN condition) into a proper `JOIN ... ON` query | 7 |
| **hard_subquery_optimize** | Hard | Replace deeply nested correlated subqueries with an efficient CTE-based approach | 10 |

---

## Reward Function

The final score is computed per the design document:

- **Easy / Medium**: `0.5 * correctness + 0.3 * efficiency + 0.2 * is_valid_sql`
- **Hard**: `0.4 * correctness + 0.4 * efficiency + 0.1 * is_valid_sql + 0.1 * uses_cte_or_window`

Additional bonuses:
- **Improvement bonus**: rewards progress over previous attempt
- **Speed bonus**: rewards solving the task early

Penalties:
- **Invalid SQL**: -0.1
- **Destructive query** (DROP/DELETE/TRUNCATE/ALTER): -1.0, episode ends
- **Semantic mismatch**: Correctness = 0.0, agent receives only minor syntax reward

Episode ends when score >= 0.95 or max attempts exceeded.

---

## Database Schema

5-table e-commerce database:

- **customers** (customer_id, name, email, city, created_at)
- **products** (product_id, name, category, price, stock)
- **orders** (order_id, customer_id, order_date, status)
- **order_items** (item_id, order_id, product_id, quantity, unit_price)
- **reviews** (review_id, customer_id, product_id, rating, review_text, created_at)

Seed data: ~100 customers, ~50 products, ~300 orders, ~600 order items, ~200 reviews (deterministic, `random.seed(42)`).

---

## Quick Start

### Option 1: Local Development

```bash
cd sql_optimizer_env
pip install -e .

# Start the server
uvicorn server.app:app --host 0.0.0.0 --port 7860

# Test all 3 tasks
uv run python scripts/test_hardcoded.py

# Run LLM inference (requires HF_TOKEN in .env)
uv run python scripts/inference.py
```

### Option 2: Docker

```bash
cd sql_optimizer_env

# Build and run
chmod +x scripts/test_docker_local.sh
./scripts/test_docker_local.sh

# In a separate terminal, test the environment
uv run python scripts/test_hardcoded.py
```

---

## Project Structure

```
sql_optimizer_env/
├── models.py              # Pydantic models: SQLAction, SQLObservation, SQLReward
├── client.py              # WebSocket client (EnvClient)
├── openenv.yaml           # Environment manifest
├── pyproject.toml         # Dependencies
├── Dockerfile             # Lightweight Python 3.10-slim build
├── .env                   # HF_TOKEN (gitignored)
├── .gitignore
├── CHANGELOG.md
├── README.md
├── scripts/
│   ├── test_hardcoded.py  # Local test for all 3 tasks
│   ├── inference.py       # LLM evaluation via Hugging Face
│   └── test_docker_local.sh  # Docker build and run helper
└── server/
    ├── __init__.py
    ├── app.py             # FastAPI server entry point
    └── sql_optimizer_environment.py  # Core RL logic
```

---

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `HF_TOKEN` | — | Hugging Face API token (required for inference.py) |
| `OPENENV_URL` | `ZeroiJ/sql-query-optimizer` | Environment server URL (HF Space or local) |
| `HF_MODEL` | `meta-llama/Meta-Llama-3-8B-Instruct` | LLM model for inference |
| `TASK_ID` | `easy_fix_select` | Task to run in inference mode |
| `NUM_EPISODES` | `1` | Number of episodes to run |

---

## License

Meta PyTorch OpenEnv Hackathon — Team Project
