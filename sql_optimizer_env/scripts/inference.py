"""Inference script for validating the SQL Optimizer environment with LLM agents.

Connects to the deployed environment, sends broken queries to a Hugging Face
model (default: Llama-3-8B-Instruct), parses the LLM's SQL responses, and
steps through the environment to collect graded rewards.
"""

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from sql_optimizer_env import SQLOptimizerEnv, SQLAction
from sql_optimizer_env.models import SQLObservation
from huggingface_hub import InferenceClient


def build_prompt(obs: SQLObservation) -> str:
    """Construct a system prompt directing the LLM to fix a broken SQL query."""
    return f"""You are a SQL optimization expert working with a SQLite e-commerce database.

DATABASE SCHEMA:
{obs.schema_description}

YOUR TASK:
Fix the following broken/inefficient SQL query. The query may have wrong column names, missing JOIN conditions, or be unnecessarily slow.

BROKEN QUERY:
{obs.broken_query}

INSTRUCTIONS:
1. Fix any syntax errors (wrong column names, missing keywords).
2. Fix any logical errors (missing JOIN conditions, cartesian products).
3. Optimize the query if possible (use JOINs instead of subqueries, add indices).
4. If you need to create indices, include CREATE INDEX statements separated by semicolons before the SELECT.

Return your answer as a JSON object with EXACTLY this field:
{{"query": "your fixed SQL query here"}}

Return ONLY the JSON object, no explanation, no markdown formatting."""


def parse_llm_response(text: str) -> SQLAction:
    """Extract JSON-wrapped SQL query from LLM response text."""
    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        raise ValueError(f"No JSON object found in response: {text}")

    data = json.loads(json_match.group())
    query = data.get("query", "")
    if not isinstance(query, str):
        raise ValueError(f"query must be a string, got {type(query)}")
    return SQLAction(query=query)


def main():
    """Entry point: run Llama-3 inference episodes against the deployed environment."""
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("Error: HF_TOKEN is not set.")
        print("Set it in your .env file or export HF_TOKEN=your_token_here")
        sys.exit(1)

    env_url = os.environ.get(
        "OPENENV_URL", "https://zeroij-sql-query-optimizer.hf.space"
    )
    model_name = os.environ.get("HF_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")
    task_id = os.environ.get("TASK_ID", "easy_fix_select")

    print(f"Connecting to environment at {env_url}...")
    print(f"Using Hugging Face model: {model_name}")
    print(f"Task: {task_id}")

    llm_client = InferenceClient(token=hf_token)
    env = SQLOptimizerEnv(base_url=env_url).sync()

    total_reward = 0.0
    num_episodes = int(os.environ.get("NUM_EPISODES", "1"))

    with env:
        for episode in range(num_episodes):
            print(f"\n{'=' * 60}")
            print(f"Episode {episode + 1}/{num_episodes}")
            print(f"{'=' * 60}")

            result = env.reset(task_id=task_id)
            obs = result.observation

            print(f"\nTask: {obs.task_id}")
            print(f"Broken Query: {obs.broken_query}")
            print(f"Max attempts: {obs.max_attempts}")

            # Multi-step loop: keep stepping until done=True
            while not obs.done:
                prompt = build_prompt(obs)

                try:
                    response = llm_client.chat_completion(
                        messages=[{"role": "user", "content": prompt}],
                        model=model_name,
                        max_tokens=500,
                        temperature=0.1,
                    )
                    response_text = response.choices[0].message.content
                    print(f"\nLLM Response:\n{response_text}")

                    action = parse_llm_response(response_text)
                    print(f"\nParsed Query: {action.query}")

                except Exception as e:
                    print(f"\nError parsing LLM response: {e}")
                    print("Falling back to broken query.")
                    action = SQLAction(query=obs.broken_query)

                result = env.step(action)
                obs = result.observation

                print(f"\n--- Attempt {obs.attempts}/{obs.max_attempts} ---")
                print(f"  Reward: {result.reward:.4f}")
                print(f"  Current Score: {obs.current_score:.4f}")
                print(f"  Correctness: {obs.metadata.get('correctness', 'N/A')}")
                print(f"  Efficiency: {obs.metadata.get('efficiency', 'N/A')}")
                print(f"  Done: {obs.done}")

                if obs.error_message:
                    print(f"  Error: {obs.error_message}")

            total_reward += result.reward
            print(f"\nEpisode complete. Final score: {obs.current_score:.4f}")

        print(f"\n{'=' * 60}")
        print(f"Total Reward: {total_reward:.2f}")
        print(f"Average Reward: {total_reward / num_episodes:.2f}")
        print(f"{'=' * 60}")

    print("\nEnvironment closed.")


if __name__ == "__main__":
    main()
