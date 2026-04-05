"""Edge case tests against the live Hugging Face Space.

Connects to the deployed SQL Optimizer environment and submits five adversarial
queries to verify grading robustness: correct queries, index spamming,
SELECT 1 exploits, destructive queries, and optimal solutions.
"""

import asyncio

from sql_optimizer_env.client import SQLOptimizerEnv
from sql_optimizer_env.models import SQLAction


async def run_test():
    """Run adversarial test cases against the deployed environment."""
    print("Connecting to cloud environment...")
    env = SQLOptimizerEnv("wss://zeroij-sql-query-optimizer.hf.space")
    task_id = "medium_slow_join"

    test_cases = [
        {
            "name": "1. The Lazy Dev (Correct data, no index)",
            "query": "SELECT customers.name, orders.order_id, orders.status FROM customers JOIN orders ON customers.customer_id = orders.customer_id WHERE orders.status = 'completed'",
        },
        {
            "name": "2. The Index Spammer (Over-indexing penalty test)",
            "query": "CREATE INDEX idx_1 ON customers(name); CREATE INDEX idx_2 ON customers(city); CREATE INDEX idx_3 ON orders(order_date); CREATE INDEX idx_4 ON orders(status); SELECT customers.name, orders.order_id, orders.status FROM customers JOIN orders ON customers.customer_id = orders.customer_id WHERE orders.status = 'completed'",
        },
        {"name": "3. The Hallucinator / Select 1 Exploit", "query": "SELECT 1;"},
        {
            "name": "4. The Destroyer (Drop Table)",
            "query": "DROP TABLE orders; SELECT customers.name, orders.order_id, orders.status FROM customers JOIN orders ON customers.customer_id = orders.customer_id WHERE orders.status = 'completed'",
        },
        {
            "name": "5. The Perfect DBA (Minimal indexing, optimal join)",
            "query": "CREATE INDEX idx_orders_status ON orders(status); SELECT customers.name, orders.order_id, orders.status FROM customers JOIN orders ON customers.customer_id = orders.customer_id WHERE orders.status = 'completed'",
        },
    ]

    for case in test_cases:
        print(f"\n{'=' * 60}")
        print(f"Executing: {case['name']}")
        print(f"Payload: {case['query'][:80]}...")

        try:
            result = await env.reset(task_id=task_id)
            obs = result.observation

            action = SQLAction(query=case["query"])
            result = await env.step(action)
            obs = result.observation
            reward = result.reward

            print(f"\nReward (value): {reward:.4f}")
            print(f"Correctness: {obs.metadata.get('correctness', 'N/A')}")
            print(f"Efficiency: {obs.metadata.get('efficiency', 'N/A')}")

            if obs.metadata.get("correctness", 0) == 0.0 or (
                isinstance(reward, float) and reward < 0
            ):
                print(
                    ">>> CAUGHT BY SEMANTIC CHECKER: Agent tried to cheat or break the DB."
                )
            elif (
                isinstance(reward, float)
                and reward < 0.9
                and obs.metadata.get("correctness", 0) == 1.0
            ):
                print(
                    ">>> CAUGHT BY HEURISTIC / PENALTY: Agent got the data, but query plan was bad or it spammed indices."
                )
            elif isinstance(reward, float) and reward >= 0.9:
                print(
                    ">>> PERFECT OPTIMIZATION: Passed semantic check and SQLite C-level execution plan cost reduction."
                )

        except Exception as e:
            print(f"Connection/Execution Error: {e}")


if __name__ == "__main__":
    asyncio.run(run_test())
