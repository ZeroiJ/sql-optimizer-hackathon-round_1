import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql_optimizer_env")
)

import asyncio
import json
from typing import List, Optional

from openai import OpenAI

try:
    from sql_optimizer_env.client import SQLOptimizerEnv
except ImportError:
    from client import SQLOptimizerEnv

try:
    from sql_optimizer_env.models import SQLAction
except ImportError:
    from models import SQLAction


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Meta-Llama-3-8B-Instruct")
OPENENV_URL = os.getenv("OPENENV_URL", "http://localhost:7860")

TASK_NAMES = ["easy_fix_select", "medium_slow_join", "hard_subquery_optimize"]
MAX_STEPS = 5


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    step: int, action: str, reward: float, done: bool, error: Optional[str]
) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


async def main():
    client = OpenAI(base_url=API_BASE_URL, api_key=OPENAI_API_KEY)

    env = SQLOptimizerEnv(OPENENV_URL)

    total_rewards = []
    total_steps = 0
    overall_success = False

    try:
        for task_name in TASK_NAMES:
            log_start(task=task_name, env="sql-query-optimizer", model=MODEL_NAME)

            rewards = []
            steps_taken = 0
            success = False

            reset_result = await env.reset(task_id=task_name)
            print("DEBUG StepResult:", dir(reset_result), flush=True)
            print(
                "DEBUG Observation:",
                getattr(reset_result, "observation", None),
                flush=True,
            )
            obs = reset_result.observation

            for step in range(1, MAX_STEPS + 1):
                prompt = f'Fix this broken SQL query: {obs.broken_query}\nSchema: {obs.schema_description}\nReturn ONLY JSON: {{"query": "your_fixed_sql"}}'

                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )

                raw_action = response.choices[0].message.content
                action_data = json.loads(raw_action)
                sql_query = action_data.get("query", "")

                result = await env.step(SQLAction(query=sql_query))

                obs = result.observation
                reward_val = float(result.reward)
                done = result.done

                rewards.append(reward_val)
                steps_taken = step

                log_step(
                    step=step,
                    action=sql_query.replace("\n", " "),
                    reward=reward_val,
                    done=done,
                    error=None,
                )

                if done:
                    if reward_val >= 0.95:
                        success = True
                    break

            final_score = max(rewards) if rewards else 0.0
            total_rewards.append(final_score)
            total_steps += steps_taken
            if success:
                overall_success = True

            log_end(
                success=success, steps=steps_taken, score=final_score, rewards=rewards
            )

    except Exception as e:
        print(f"Error during inference: {e}")
    finally:
        await env.close()


if __name__ == "__main__":
    asyncio.run(main())
