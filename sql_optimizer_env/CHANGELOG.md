# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 3-task system (Easy/Medium/Hard) aligned with team design doc
  - `easy_fix_select` (5 attempts): Fix broken column names
  - `medium_slow_join` (7 attempts): Rewrite cartesian product to proper JOIN
  - `hard_subquery_optimize` (10 attempts): Replace nested subqueries with CTE
- 5-table e-commerce schema: `customers`, `products`, `orders`, `order_items`, `reviews`
- `_seed_data()`: deterministic dummy data (~100 customers, ~50 products, ~300 orders, ~600 items, ~200 reviews)
- `_verify_semantic_equivalence()`: compares agent query vs expected fix results
- `_calculate_query_cost()` heuristics: SCAN=100, SEARCH=10, TEMP B-TREE=50, AUTOMATIC INDEX=75, CORRELATED SCALAR SUBQUERY=150, COVERING INDEX=-20
- Reward formula per design doc: `0.5*correctness + 0.3*efficiency + 0.2*is_valid_sql` (+ improvement + speed bonuses)
- Destructive query detection (DROP/DELETE/TRUNCATE/ALTER) → -1.0 penalty, episode ends
- Invalid SQL penalty: -0.1
- `SQLReward` class with `value`, `correctness`, `efficiency`, `is_valid_sql`, `done`, `info`
- `openenv.yaml` updated with observation_space, action_space, reward_range, tasks metadata

### Changed
- `SQLAction`: `optimized_query` + `indices_to_create` → single `query` field
- `SQLObservation`: `database_schema`/`table_statistics`/`raw_query` → `task_id`/`schema_description`/`broken_query`/`current_score`/`attempts`/`max_attempts`
- `step()` returns `SQLObservation` (OpenEnv API) with reward/done/info embedded in metadata
- `scripts/test_hardcoded.py` and `scripts/inference.py` updated for new models
- `openenv.yaml`: name → `sql-query-optimizer`, version → `1.0.0`

### Fixed
- `EnvClient` generic type: added missing `State` parameter
- Scripts use `.sync()` wrapper for synchronous client usage
- Index name extraction: regex handles `CREATE UNIQUE INDEX` and `CREATE INDEX IF NOT EXISTS`

## [0.1.0] - 2026-04-04

### Added
- Initial project release — SQL Query Optimizer OpenEnv RL Environment
- `SQLOptimizerEnvironment` class with `reset()` and `step()` methods
- `SQLAction` model (`optimized_query`, `indices_to_create`)
- `SQLObservation` model (`database_schema`, `table_statistics`, `raw_query`, `initial_cost`, `optimized_cost`, `error_message`)
- `SQLOptimizerEnv` WebSocket client extending `EnvClient`
- EXPLAIN QUERY PLAN cost-heuristic reward function
- `ecommerce_orders` mock table (id, user_id, total_amount, status, created_at)
- `test_hardcoded.py` — local WebSocket test with hardcoded optimal action
- `inference.py` — Hugging Face model evaluation script (HF_TOKEN, InferenceClient, Llama-3-8B-Instruct)
- Root-level `Dockerfile` (multi-stage build from `openenv-base`)
- `openenv.yaml` manifest (name: `sql-optimizer-env`, version: `0.1.0`)
- `pyproject.toml` with openenv-core, fastapi, pydantic, uvicorn, huggingface-hub dependencies

### Changed
- Reward calculation: `initial_cost - new_cost` (cost-heuristic based, not execution-time based)

### Removed
- Execution-time measurement (`_measure_query_time`, `original_execution_time_ms`, `optimized_execution_time_ms`)
- Multi-schema templates (inventory, logging) — consolidated to single `ecommerce_orders` table
- Mock data generation (`_generate_mock_data`) — not needed for cost-heuristic approach

### Notes
- No OpenAI API keys — HF_TOKEN only
- Statelessness: all created indices dropped after each step
- Single-step bandit episode (`done=True` after one step)
