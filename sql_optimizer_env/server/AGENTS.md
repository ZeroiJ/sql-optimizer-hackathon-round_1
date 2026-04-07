# sql_optimizer_env/server

**Part of:** sql-optimizer project

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Core RL logic | `sql_optimizer_environment.py` | 547 lines - grading, reward computation |
| FastAPI entry | `app.py` | create_app wrapper |

## CONVENTIONS
- Uses OpenEnv's `create_app()` factory pattern
- Environment class extends `Environment` base
- Synchronous reset/step methods

## ANTI-PATTERNS (THIS DIR)
- **No async in environment**: Use sync methods, wrapped by server
- **No direct DB writes**: All via SQLite connection in environment

## KEY FUNCTIONS
- `_calculate_query_cost()` - EXPLAIN QUERY PLAN heuristics
- `_seed_data()` - Deterministic data (random.seed(42))
- `TASKS` dict - Task definitions with expected queries