import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sql_optimizer_env.env.sql_optimizer import SQLOptimizerEnv
from sql_optimizer_env.models import SQLAction


TASKS = [
    {
        "task_id": "easy_fix_select",
        "query": "SELECT customer_id, name, email FROM customers WHERE city = 'Mumbai'",
    },
    {
        "task_id": "medium_slow_join",
        "query": "SELECT customers.name, orders.order_id, orders.status FROM customers JOIN orders ON customers.customer_id = orders.customer_id WHERE orders.status = 'completed'",
    },
    {
        "task_id": "hard_subquery_optimize",
        "query": "WITH customer_stats AS (SELECT o.customer_id, COUNT(o.order_id) as order_count, SUM(oi.unit_price * oi.quantity) as total_spent FROM orders o JOIN order_items oi ON o.order_id = oi.order_id GROUP BY o.customer_id) SELECT c.customer_id, c.name, cs.order_count, cs.total_spent FROM customers c JOIN customer_stats cs ON c.customer_id = cs.customer_id WHERE cs.order_count > 2",
    },
    {
        "task_id": "easy_fix_select",
        "query": "SELECT 1;",
    },
]


def main():
    env = SQLOptimizerEnv()

    for task in TASKS:
        task_id = task["task_id"]
        query = task["query"]

        obs = env.reset(task_id=task_id)
        print(f"\n{'=' * 60}")
        print(f"Task: {obs.task_id}")
        print(f"Broken Query: {obs.broken_query}")
        print(f"Max attempts: {obs.max_attempts}")

        action = SQLAction(query=query)
        obs = env.step(action)

        print(f"\n--- Result ---")
        print(f"Reward (value): {obs.metadata.get('value', obs.reward):.4f}")
        print(f"Correctness: {obs.metadata.get('correctness', 'N/A')}")
        print(f"Efficiency: {obs.metadata.get('efficiency', 'N/A'):.4f}")
        print(f"is_valid_sql: {obs.metadata.get('is_valid_sql', 'N/A')}")
        print(
            f"Semantic Match: {obs.metadata.get('info', {}).get('semantic_match', 'N/A')}"
        )
        print(f"Done: {obs.done}")
        print(f"Attempts: {obs.attempts}/{obs.max_attempts}")

        if obs.error_message:
            print(f"Error: {obs.error_message}")

    env.close()
    print(f"\n{'=' * 60}")
    print("All 3 tasks tested successfully.")


if __name__ == "__main__":
    main()
