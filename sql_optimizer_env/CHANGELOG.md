# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-04-25

### Added
- **Modular Reward System** (`env/rewards/`)
  - Introduced isolated reward modules with strict interfaces:
    - `base.py`: abstract `BaseReward.calculate(...)` contract
    - `correctness.py`: binary semantic signal (`1.0` match, `-1.0` mismatch)
    - `efficiency.py`: continuous execution-time delta reward in `[-1.0, 1.0]`
    - `style.py`: SQL quality heuristic reward (`0.5` or `0.0`)
    - `anticheat.py`: strong penalty for unsafe SQL (`-5.0`)
  - Added reward orchestrator in `env/rewards/__init__.py` to compute all
    dimensions independently and aggregate total reward with explicit errors.

- **Discriminated Action Space** (`models.py`)
  - Replaced generic `SQLAction` with strict action variants:
    - `RewriteQueryAction(action_type="rewrite_query", new_sql)`
    - `CreateIndexAction(action_type="create_index", table_name, column_name)`
  - Added `AgentAction` discriminated union via `Field(discriminator="action_type")`.
  - Extended `SQLObservation` with `schema_diff: list[str]` for schema drift/index tracking.

- **Schema Drift Chaos Layer** (`env/schema_drift.py`)
  - Added `SchemaDrifter` for reset-time chaos mutations against PostgreSQL:
    - drop random non-primary index
    - toggle `reviews.rating` ↔ `reviews.stars`
    - alter `products.name` to `TEXT`
  - Added `heal_schema()` to repair schema via DDL-only changes (no reseeding).

### Changed
- **Environment Integration**
  - `reset()` now includes a 20% schema-drift trigger and reports drift events in observation `schema_diff`
  - `step()` now parses discriminated `AgentAction` payloads and executes action-specific paths for SQL rewrite vs index creation
  - Reward computation in `step()` moved to the modular 4-signal reward stack with per-signal metadata (`correctness`, `efficiency`, `style`, `anticheat`)

## [2.0.0] - 2026-04-25

### Added
- **Major Migration**: SQLite → PostgreSQL for production-grade database workloads
  - Replaced `sqlite3` with `psycopg2` for database connectivity
  - Connection string: `postgresql://admin:admin@localhost:5432/dbre_env`
  - Schema DDL updated for PostgreSQL syntax (`SERIAL`, `TIMESTAMP`, `NUMERIC`)

- **Query Analysis**: Rewrote cost estimation to use `EXPLAIN (ANALYZE, FORMAT JSON)`
  - Replaced heuristics-based `_calculate_query_cost()` with JSON-parsing `_explain_analyze_json()`
  - Extracts `Execution Time` and `Total Cost` from PostgreSQL's native query planner
  - Returns structured dict with `execution_time_ms`, `plan`, and `total_cost`

- **Data Seeding**: Complete rewrite using PostgreSQL `generate_series()`
  - Eliminated all Python loops from `_seed_data()`
  - Server-side generation scales to larger datasets:
    - 10,000 customers (was 100)
    - 5,000 products (was 50)
    - 100,000 orders (was 300)
    - 500,000 order_items (was 600)
    - 50,000 reviews (was 200)

### Added
- **Workload Generator** (`env/workload_generator.py`)
  - New `WorkloadGenerator` class for dynamic slow query injection
  - `generate_slow_query()` returns randomized unoptimized SQL from 3 templates:
    1. **N+1 Join Trap**: Multi-table join with `LIKE '%Product_%'` filter on unindexed text column
    2. **Sequential Scan**: Aggregation on `order_items.unit_price` forcing full table scan
    3. **Bad Subquery**: `WHERE IN (SELECT...)` anti-pattern on reviews table
  - Each template includes randomized parameters (cities, price thresholds, ratings)

- **Environment Integration**
  - `reset()` method now supports `use_workload_generator: bool` parameter
  - When enabled, environment generates dynamic slow queries instead of hardcoded TASKS
  - Maintains backward compatibility with existing task IDs

### Dependencies
- Added `psycopg2-binary>=2.9.0` to `pyproject.toml` and `Dockerfile`
- Dockerfile updated to install `libpq5` instead of `sqlite3`

## [1.0.0] - 2026-04-08

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
