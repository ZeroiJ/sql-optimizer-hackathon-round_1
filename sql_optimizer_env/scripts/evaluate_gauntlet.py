"""Gauntlet test suite - Evaluate RL environment robustness with edge cases."""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from sql_optimizer_env.client import SQLOptimizerEnv
from sql_optimizer_env.models import SQLAction

SPACE_ID = "ZeroiJ/sql-query-optimizer"
TASK_NAME = "medium_slow_join"

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

COLORS = {
    "red": "\033[0;31m",
    "green": "\033[0;32m",
    "yellow": "\033[0;33m",
    "blue": "\033[0;34m",
    "magenta": "\033[0;35m",
    "cyan": "\033[0;36m",
    "white": "\033[0;37m",
    "pink": "\033[38;5;201m",
    "orange": "\033[38;5;208m",
    "purple": "\033[38;5;141m",
}


def color(text: str, color_name: str) -> str:
    return f"{COLORS.get(color_name, '')}{text}{RESET}"


def box(title: str, content: str, width: int = 70) -> str:
    lines = content.split("\n")
    return (
        f"{color('═' * width, 'cyan')}\n"
        f"{color(title.center(width), 'cyan')}\n"
        f"{color('═' * width, 'cyan')}\n"
        + "\n".join(
            f"{color('│', 'cyan')} {line:<{width - 2}} {color('│', 'cyan')}"
            for line in lines
        )
        + f"\n{color('═' * width, 'cyan')}"
    )


GAUNTLET = [
    {
        "name": "The Garbage Injector",
        "description": "Tests SQL injection/parser robustness with random text",
        "query": "SELECT * FROM ducks WHERE quack = true; DROP DATABASE;",
        "expected": "Should reject as invalid SQL or return low reward",
    },
    {
        "name": "The Cartesian Exploder",
        "description": "Tests C-level SQLite cost engine with massive unoptimized scan",
        "query": "SELECT * FROM customers CROSS JOIN orders;",
        "expected": "High cost due to cartesian product, low efficiency score",
    },
    {
        "name": "The Schema Hallucinator",
        "description": "Tests semantic grader with non-existent columns",
        "query": "SELECT user_id, secret_password FROM customers WHERE status = 'active';",
        "expected": "Should fail semantic check - columns don't exist",
    },
    {
        "name": "The Perfect Optimizer",
        "description": "Optimal query with index for maximum score",
        "query": "CREATE INDEX idx_orders_status ON orders(status); SELECT customers.name, orders.order_id, orders.status FROM customers JOIN orders ON customers.customer_id = orders.customer_id WHERE orders.status = 'completed';",
        "expected": "High correctness + high efficiency = max score",
    },
]


async def run_gauntlet():
    print(f"\n{color('🎯 THE SQL OPTIMIZER GAUNTLET 🎯', 'pink')}")
    print(f"{color('=' * 70, 'cyan')}")
    print(f"{color('Testing environment robustness against edge cases', 'white')}")
    print(f"{color(f'Space: {SPACE_ID}', 'dim')}")
    print(f"{color(f'Task: {TASK_NAME}', 'dim')}")
    print()

    env = SQLOptimizerEnv(f"wss://zeroij-sql-query-optimizer.hf.space")
    results: List[Dict[str, Any]] = []

    try:
        for i, scenario in enumerate(GAUNTLET, 1):
            print(f"{color(f'⚔️  Test {i}: {scenario['name']}', 'yellow')}")
            print(f"    {color(scenario['description'], 'white')}")

            try:
                reset_result = await env.reset(task_id=TASK_NAME)
                obs = reset_result.observation

                action = SQLAction(query=scenario["query"])
                step_result = await env.step(action)

                obs = step_result.observation
                reward_val = (
                    float(step_result.reward) if step_result.reward is not None else 0.0
                )
                done = step_result.done

                correctness = obs.metadata.get("correctness", 0.0)
                efficiency = obs.metadata.get("efficiency", 0.0)
                is_valid_sql = obs.metadata.get("is_valid_sql", True)
                error_msg = obs.error_message

                results.append(
                    {
                        "name": scenario["name"],
                        "query": scenario["query"],
                        "reward": reward_val,
                        "correctness": correctness,
                        "efficiency": efficiency,
                        "is_valid_sql": is_valid_sql,
                        "error": error_msg,
                        "done": done,
                    }
                )

                score_color = (
                    "green"
                    if reward_val >= 0.9
                    else "yellow"
                    if reward_val >= 0.5
                    else "red"
                )
                print(f"    {color('─' * 50, 'dim')}")
                print(f"    Reward:   {color(f'{reward_val:.4f}', score_color)}")
                print(
                    f"    Correct:  {color(f'{correctness:.2f}', 'cyan')} | "
                    f"{color(f'Efficiency: {efficiency:.2f}', 'cyan')}"
                )
                print(f"    Valid SQL: {color(str(is_valid_sql), 'cyan')}")

                if error_msg:
                    print(f"    {color(f'Error: {error_msg}', 'red')}")
                if done:
                    print(f"    {color('Episode terminated', 'magenta')}")

            except Exception as e:
                print(f"    {color(f'Exception: {str(e)}', 'red')}")
                results.append(
                    {
                        "name": scenario["name"],
                        "query": scenario["query"],
                        "reward": -1.0,
                        "correctness": 0.0,
                        "efficiency": 0.0,
                        "is_valid_sql": False,
                        "error": str(e),
                        "done": False,
                    }
                )

            print()

    finally:
        await env.close()

    print(box("📊 GAUNTLET RESULTS SUMMARY", ""))
    print()

    header = (
        f"{'Test':<25} {'Reward':>8} {'Correct':>8} {'Efficient':>10} {'Status':>10}"
    )
    print(f"{color(header, 'bold')}")
    print(f"{color('─' * 70, 'dim')}")

    for r in results:
        status = (
            "✅ PASS"
            if r["reward"] >= 0.9
            else "⚠️  PARTIAL"
            if r["reward"] >= 0.5
            else "❌ FAIL"
        )
        status_color = (
            "green" if r["reward"] >= 0.9 else "yellow" if r["reward"] >= 0.5 else "red"
        )

        row = f"{r['name'][:24]:<25} {r['reward']:>8.4f} {r['correctness']:>8.2f} {r['efficiency']:>10.2f} {color(status, status_color):>10}"
        print(row)

    print(f"{color('─' * 70, 'dim')}")

    total_reward = sum(r["reward"] for r in results)
    avg_reward = total_reward / len(results) if results else 0.0

    print()
    print(f"{color('📈 OVERALL STATS', 'bold')}")
    print(f"  Total Tests: {len(results)}")
    print(f"  Avg Reward:  {color(f'{avg_reward:.4f}', 'cyan')}")
    print(f"  Total Score: {color(f'{total_reward:.4f}', 'cyan')}")
    print()

    passed = sum(1 for r in results if r["reward"] >= 0.9)
    partial = sum(1 for r in results if 0.5 <= r["reward"] < 0.9)
    failed = sum(1 for r in results if r["reward"] < 0.5)

    print(f"  {color('✅ Passed:', 'green')}  {passed}")
    print(f"  {color('⚠️  Partial:', 'yellow')} {partial}")
    print(f"  {color('❌ Failed:', 'red')}  {failed}")
    print()

    return results


if __name__ == "__main__":
    asyncio.run(run_gauntlet())
