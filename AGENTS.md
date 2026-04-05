# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-04
**Branch:** main

## OVERVIEW
SQL Query Optimizer — OpenEnv RL Environment for the Meta PyTorch Hackathon. Trains LLM agents to rewrite poorly-optimized SQL queries and suggest indices on SQLite databases. Built on OpenEnv (meta-pytorch/OpenEnv) with FastAPI + WebSocket server.

## STRUCTURE
```
./
├── sql_optimizer_env/          # Python package (OpenEnv environment)
│   ├── models.py               # SQLAction, SQLObservation Pydantic models
│   ├── client.py               # WebSocket client (extends EnvClient[Act, Obs, State])
│   ├── __init__.py             # Package exports
│   ├── openenv.yaml            # Environment manifest (name: sql-optimizer-env)
│   ├── pyproject.toml          # Dependencies + build config
│   ├── Dockerfile              # Multi-stage build (root-level, not server/)
│   ├── .env                    # HF_TOKEN persistence (NEVER commit)
│   ├── .gitignore              # Excludes .env, __pycache__, .venv, *.egg-info
│   ├── CHANGELOG.md            # Version history
│   ├── README.md               # Docs
│   ├── scripts/
│   │   ├── inference.py        # LLM validation script (HF_TOKEN, dotenv, Llama-3-8B)
│   │   └── test_hardcoded.py   # Local test with hardcoded optimal action
│   └── server/
│       ├── app.py              # FastAPI server via create_app()
│       ├── sql_optimizer_environment.py  # Core RL logic — EXPLAIN QUERY PLAN cost heuristic
│       └── __init__.py
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Define action/observation schema | `models.py` | SQLAction, SQLObservation |
| Core RL logic (reset, step, reward) | `server/sql_optimizer_environment.py` | 514 lines, in-memory SQLite |
| FastAPI server entry point | `server/app.py` | `create_app()` factory |
| WebSocket client | `client.py` | Extends `EnvClient` |
| Validation / inference | `scripts/inference.py` | Uses HF_TOKEN, not OpenAI |
| Local testing | `scripts/test_hardcoded.py` | Hardcoded optimal action |
| Docker build | `Dockerfile` | Root-level, based on `openenv-base` |

## CONVENTIONS
- Relative imports use try/except fallback for both in-repo and standalone modes
- `SUPPORTS_CONCURRENT_SESSIONS = True` on environment class
- Dockerfile placed in root (not `server/`) per user requirement
- `inference.py` uses `huggingface_hub.login()` — never OpenAI keys
- Reward: `(initial_cost - new_cost) - (num_indices * 15.0)` via EXPLAIN QUERY PLAN heuristics
  - SCAN=100, SEARCH=10, USE TEMP B-TREE=50, AUTOMATIC INDEX=75, CORRELATED SCALAR SUBQUERY=150, COVERING INDEX=-20
  - Semantic equivalence check: -500.0 penalty if optimized query returns different results
  - Index penalty: 15.0 per CREATE INDEX statement

## ANTI-PATTERNS
- Never use `as any` or suppress type errors
- Never skip index cleanup after step (statelessness required)
- Never use OpenAI API keys — HF_TOKEN only
- Never place Dockerfile in `server/` — must be root-level

## COMMANDS
```bash
# Install
cd sql_optimizer_env && pip install -e .

# Start server
uvicorn server.app:app --host 0.0.0.0 --port 8000

# Run validation
python scripts/inference.py

# Run local test
python scripts/test_hardcoded.py

# Build Docker
docker build -t sql-optimizer-env:latest .
```

## NOTES
- SQLite uses `:memory:` databases — each reset creates a fresh DB with 500 mock rows
- Single table: `ecommerce_orders` (id, user_id, total_amount, status, created_at)
- Reward via EXPLAIN QUERY PLAN: SCAN=100, SEARCH=10, USE TEMP B-TREE=50, error=10000
- Semantic equivalence: both queries must return identical results, else -500.0 penalty
- Index penalty: 15.0 per CREATE INDEX statement
- Indices created during step are dropped before returning to maintain statelessness
