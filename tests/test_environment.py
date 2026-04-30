import pytest
from sql_optimizer_env.server.sql_optimizer_environment import SQLOptimizerEnv
from sql_optimizer_env.models import RewriteQueryAction as SQLAction


def test_reset():
    env = SQLOptimizerEnv()
    obs = env.reset()
    # SQLObservation exposes broken_query directly.
    assert hasattr(obs, "broken_query"), "Observation missing 'broken_query' attribute"
    assert obs.broken_query is not None, "Broken query should not be None"
    assert isinstance(obs.reward, float)


def test_step_valid_query():
    env = SQLOptimizerEnv()
    env.reset()
    # Step expects action objects, not raw strings.
    action = SQLAction(action_type="rewrite_query", new_sql="SELECT customer_id FROM customers;")
    obs = env.step(action)
    assert isinstance(obs.reward, float)


def test_step_invalid_query():
    env = SQLOptimizerEnv()
    env.reset()
    action = SQLAction(action_type="rewrite_query", new_sql="NOT A VALID SQL")
    obs = env.step(action)
    assert isinstance(obs.reward, float)
    assert obs.error_message is not None


def test_reward_range_across_episodes():
    env = SQLOptimizerEnv()
    test_queries = [
        "SELECT customer_id FROM customers;",
        "DROP TABLE users;",
        "SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id;",
        "INVALID SQL HERE",
    ]

    for difficulty in ["easy", "medium", "hard"]:
        env.difficulty = difficulty
        for query in test_queries:
            env.reset()
            action = SQLAction(action_type="rewrite_query", new_sql=query)
            obs = env.step(action)
            assert isinstance(obs.reward, float), (
                f"Failed on {difficulty} with query '{query}': reward={obs.reward}"
            )


def test_action_model_required():
    """Verify step() handles raw strings as invalid payloads."""
    env = SQLOptimizerEnv()
    env.reset()
    obs = env.step("just a string, not SQLAction")
    assert obs.error_message is not None
