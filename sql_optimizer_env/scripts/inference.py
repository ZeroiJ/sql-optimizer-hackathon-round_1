"""Inference script for validating the SQL Optimizer environment with LLM agents.

Connects to the deployed environment, iterations through the tasks, sends broken queries
to a Hugging Face model via the router, parses the responses, and steps through the environment
to collect graded rewards.
"""

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent))

from sql_optimizer_env.env.sql_optimizer import SQLOptimizerEnv
from sql_optimizer_env.models import SQLAction, SQLObservation


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
    """Entry point: run LLM inference episodes against the OpenEnv environment."""
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("Error: HF_TOKEN is not set.")
        print("Set it in your .env file or export HF_TOKEN=your_token_here")
        sys.exit(1)

    model_name = os.environ.get("HF_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")

    # 1. Use the Hugging Face Router
    llm_client = InferenceClient(token=hf_token)

    # Connect to the environment (local direct instantiation since it's the mandatory script logic)
    print(f"Connecting to local environment...")
    print(f"Using Hugging Face model: {model_name}")

    env = SQLOptimizerEnv()

    # 2. Iterate through the exactly 3 tasks
    tasks = ["easy_fix_select", "medium_slow_join", "hard_subquery_optimize"]

    total_reward = 0.0

    print(f"\n{'=' * 60}")
    print(f"Starting Inference across all 3 tasks")
    print(f"{'=' * 60}")

    for task_id in tasks:
        print(f"\nTesting Task: {task_id}")

        obs: SQLObservation = env.reset(task_id=task_id)

        print(f"Broken Query: {obs.broken_query}")
        print(f"Max attempts: {obs.max_attempts}")

        while not obs.done:
            # 4. Mandatory System Prompt
            system_prompt = 'You are a Senior DBA. Fix the provided broken SQL query. Return ONLY a JSON object with the "query" key.'
            user_prompt = f"Schema:\n{obs.schema_description}\n\nBroken Query:\n{obs.broken_query}"

            try:
                response = llm_client.chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=model_name,
                    max_tokens=500,
                    temperature=0.1,
                )
                response_text = response.choices[0].message.content
                print(f"\nLLM Response:\n{response_text}")

                action = parse_llm_response(response_text)
                print(f"\nParsed Query: {action.query}")

            except Exception as e:
                print(f"\nError interacting with LLM: {e}")
                print("Falling back to broken query.")
                action = SQLAction(query=obs.broken_query)

            obs = env.step(action)

            print(f"\n--- Attempt {obs.attempts}/{obs.max_attempts} ---")
            print(f"  Reward: {obs.reward:.4f}")
            print(f"  Current Score: {obs.current_score:.4f}")
            print(f"  Correctness: {obs.metadata.get('correctness', 'N/A')}")
            print(f"  Efficiency: {obs.metadata.get('efficiency', 'N/A')}")
            print(f"  Done: {obs.done}")

            if obs.error_message:
                print(f"  Error: {obs.error_message}")

        total_reward += obs.current_score
        print(f"\nTask {task_id} complete. Final score: {obs.current_score:.4f}")
        print("-" * 60)

    print(f"\n{'=' * 60}")
    print(f"Overall Total Reward: {total_reward:.2f}/{len(tasks)}")
    print(f"{'=' * 60}")

    env.close()


if __name__ == "__main__":
    main()
