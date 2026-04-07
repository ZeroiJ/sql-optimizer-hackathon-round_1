# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-08
**Commit:** 1b00977
**Branch:** master

## OVERVIEW
SQL Query Optimizer RL Environment for Meta PyTorch OpenEnv Hackathon. Teaches LLM agents to fix/optimize SQL queries against a SQLite e-commerce database.

## STRUCTURE
```
sql-optimizer/
├── sql_optimizer_env/       # Main package
│   ├── scripts/            # Test & inference scripts
│   │   ├── evaluate_gauntlet.py
│   │   ├── inference.py
│   │   ├── test_edge_cases.py
│   │   └── test_hardcoded.py
│   ├── server/             # FastAPI server
│   │   ├── app.py
│   │   └── sql_optimizer_environment.py
│   ├── client.py           # WebSocket client
│   ├── models.py           # Pydantic models
│   ├── env/                # Local env (legacy)
│   └── openenv.yaml        # Environment manifest
├── validate-submission.sh  # HF Space validator
└── README.md
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| RL Environment | `sql_optimizer_env/server/sql_optimizer_environment.py` | Core grading logic |
| API Server | `sql_optimizer_env/server/app.py` | FastAPI + OpenEnv |
| Models | `sql_optimizer_env/models.py` | SQLAction, SQLObservation, SQLReward |
| Client | `sql_optimizer_env/client.py` | WebSocket client |
| Run server | `uvicorn sql_optimizer_env.server.app:app` | Local dev |

## CONVENTIONS
- **Python**: >=3.10, pydantic>=2.0
- **Server port**: 7860 (default for HF Spaces) or 8000 (local)
- **Tasks**: easy_fix_select, medium_slow_join, hard_subquery_optimize
- **Grading**: 0.5*correctness + 0.3*efficiency + 0.2*is_valid_sql

## ANTI-PATTERNS (THIS PROJECT)
- **No destructive queries**: DROP, DELETE, TRUNCATE penalized -1.0
- **No type suppression**: Never use `as any`, `@ts-ignore`
- **No empty catch**: Always handle exceptions meaningfully

## COMMANDS
```bash
# Local server
cd sql_optimizer_env && uvicorn server.app:app --host 0.0.0.0 --port 7860

# Run tests
cd sql_optimizer_env && python scripts/test_hardcoded.py
python scripts/evaluate_gauntlet.py

# Validate HF Space
./validate-submission.sh https://zeroij-sql-query-optimizer.hf.space
```

## NOTES
- **3 tasks** with max_attempts: easy=5, medium=7, hard=10
- **Reward formula** varies by task difficulty
- **Semantic check**: executes both queries, sets Correctness to 0.0 on mismatch
- **Cost heuristics**: SCAN +100, SEARCH +10, TEMP B-TREE +50
