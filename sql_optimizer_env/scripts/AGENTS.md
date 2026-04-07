# sql_optimizer_env/scripts

**Part of:** sql-optimizer project

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Hardcoded tests | `test_hardcoded.py` | Local env test |
| Edge case tests | `test_edge_cases.py` | Live HF Space test |
| Inference script | `inference.py` | LLM evaluation |
| Gauntlet | `evaluate_gauntlet.py` | Robustness testing |

## CONVENTIONS
- Scripts use `sys.path.insert(0, ...)` for imports
- Test scripts connect to live HF Space via WebSocket
- All scripts use `asyncio` for async operations

## ANTI-PATTERNS (THIS DIR)
- **Broken imports in test_hardcoded.py**: Uses wrong import path
- **No error handling in inference.py**: json.loads can crash on malformed LLM response