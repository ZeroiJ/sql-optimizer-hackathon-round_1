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

![Tests](https://github.com/ZeroiJ/sql-optimizer-hackathon-round_1/actions/workflows/test.yml/badge.svg)

A practical RL-style environment where an agent fixes and optimizes SQL queries on an e-commerce schema.
It is built for fast local iteration, reproducible testing, and easy demoing.

---

## Why this project

- Learn and evaluate query-rewrite behavior with concrete reward signals.
- Test locally with SQLite fallback (`USE_SQLITE=1`) and no external DB setup.
- Keep CI simple and deterministic.
- Showcase a clean ML-systems style project in a portfolio.

---

## Quick start (2 minutes)

From repo root:

```bash
cd sql_optimizer_env
pip install -e ".[dev]"
```

Run tests (recommended):

```bash
cd ..
USE_SQLITE=1 pytest tests/ -v
```

Run a quick smoke check:

```bash
USE_SQLITE=1 python -c "from sql_optimizer_env.server.sql_optimizer_environment import SQLOptimizerEnvironment; from sql_optimizer_env.models import RewriteQueryAction; env = SQLOptimizerEnvironment(); obs = env.reset(); print('Broken query:', obs.broken_query[:100]); res = env.step(RewriteQueryAction(action_type='rewrite_query', new_sql='SELECT customer_id FROM customers;')); print('Reward:', res.reward)"
```

---

## Tasks

| Task ID | Difficulty | Max Attempts | Goal |
|---|---|---:|---|
| `easy_fix_select` | Easy | 5 | Fix obvious column/typo issues |
| `medium_slow_join` | Medium | 7 | Replace inefficient/cartesian join patterns |
| `hard_subquery_optimize` | Hard | 10 | Rewrite complex subquery-heavy SQL |

---

## Reward model

Rewards combine correctness, efficiency, and SQL validity:

- Easy / Medium: `0.5 * correctness + 0.3 * efficiency + 0.2 * is_valid_sql`
- Hard: `0.4 * correctness + 0.4 * efficiency + 0.1 * is_valid_sql + 0.1 * uses_cte_or_window`

The environment also tracks progress bonuses and ends an episode when:
- `score >= 0.95`, or
- `max_attempts` is reached.

---

## Data model

Schema uses 5 e-commerce tables:
- `customers`
- `products`
- `orders`
- `order_items`
- `reviews`

The environment supports:
- PostgreSQL mode (when configured and reachable)
- SQLite in-memory fallback (great for tests/CI)

---

## Run the server

```bash
cd sql_optimizer_env
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

---

## Repo layout

```text
.
├── sql_optimizer_env/
│   ├── client.py
│   ├── models.py
│   ├── openenv.yaml
│   ├── pyproject.toml
│   ├── scripts/
│   └── server/
│       ├── app.py
│       └── sql_optimizer_environment.py
├── tests/
├── .github/workflows/test.yml
├── CONTRIBUTING.md
└── LICENSE
```

---

## Useful commands

Run only environment tests:
```bash
USE_SQLITE=1 pytest tests/test_environment.py -v
```

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `USE_SQLITE` | `0` | Set to `1` to force in-memory SQLite fallback |
| `DATABASE_URL` | `postgresql://admin:admin@localhost:5432/dbre_env` | PostgreSQL URL for primary runtime |

---

## Contributing

Friendly PRs welcome. See `CONTRIBUTING.md` for setup and workflow.

---

## License

MIT. See `LICENSE`.
