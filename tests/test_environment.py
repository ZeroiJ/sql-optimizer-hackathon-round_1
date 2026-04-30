import pytest
from sql_optimizer_env.server.sql_optimizer_environment import SQLOptimizerEnv


def test_reset():
    env = SQLOptimizerEnv()
    obs = env.reset()
    assert 0.0 <= obs.reward <= 1.0, f"Reward {obs.reward} out of range"
    assert obs.observation["query"] is not None


def test_step_valid_query():
    env = SQLOptimizerEnv()
    env.reset()
    obs = env.step("SELECT * FROM users;")
    assert 0.0 <= obs.reward <= 1.0


def test_step_invalid_query():
    env = SQLOptimizerEnv()
    env.reset()
    obs = env.step("NOT A VALID SQL")
    assert 0.0 <= obs.reward <= 1.0


def test_reward_range_across_episodes():
    env = SQLOptimizerEnv()
    for difficulty in ["easy", "medium", "hard"]:
        env.difficulty = difficulty
        for _ in range(10):
            env.reset()
            obs = env.step("SELECT * FROM users;")
            assert 0.0 <= obs.reward <= 1.0, f"Failed on {difficulty}"
