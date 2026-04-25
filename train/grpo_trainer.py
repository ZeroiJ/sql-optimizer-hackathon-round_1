"""GRPO training entrypoint bridging TRL with the OpenEnv SQL environment."""

import json
from typing import Any

from datasets import Dataset
from pydantic import TypeAdapter, ValidationError
from trl import GRPOConfig, GRPOTrainer

from train.model_loader import load_qwen_unsloth

try:
    from sql_optimizer_env.models import AgentAction
    from sql_optimizer_env.server.sql_optimizer_environment import SQLOptimizerEnvironment
except ImportError:
    from models import AgentAction
    from server.sql_optimizer_environment import SQLOptimizerEnvironment


def _extract_completion_text(completion: Any) -> str:
    """Extract assistant text from TRL completion payload variants."""
    if isinstance(completion, str):
        return completion
    if isinstance(completion, dict):
        content = completion.get("content", "")
        return content if isinstance(content, str) else ""
    if isinstance(completion, list) and completion:
        last = completion[-1]
        if isinstance(last, dict):
            content = last.get("content", "")
            return content if isinstance(content, str) else ""
        if isinstance(last, str):
            return last
    return ""


def openenv_reward_func(
    prompts: list[str],
    completions: list[list[dict]],
    **kwargs: Any,
) -> list[float]:
    """Score each completion by executing validated actions in OpenEnv."""
    _ = prompts, kwargs
    rewards: list[float] = []
    action_adapter = TypeAdapter(AgentAction)

    for completion in completions:
        completion_text = _extract_completion_text(completion).strip()
        if not completion_text:
            rewards.append(-2.0)
            continue

        try:
            completion_json = json.loads(completion_text)
            parsed_action = action_adapter.validate_python(completion_json)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
            rewards.append(-2.0)
            continue

        env = SQLOptimizerEnvironment()
        try:
            env.reset(use_workload_generator=True)
            step_observation = env.step(parsed_action)
            metadata = getattr(step_observation, "metadata", {}) or {}
            correctness = float(metadata.get("correctness", 0.0))
            efficiency = float(metadata.get("efficiency", 0.0))
            style = float(metadata.get("style", 0.0))
            anticheat = float(metadata.get("anticheat", 0.0))
            rewards.append(correctness + efficiency + style + anticheat)
        except Exception:
            rewards.append(-2.0)
        finally:
            env.close()

    return rewards


def main() -> None:
    """Run GRPO training against the SQL OpenEnv reward source."""
    model, tokenizer = load_qwen_unsloth()
    train_dataset = Dataset.from_dict({"prompt": [""] * 10})

    training_args = GRPOConfig(
        output_dir="outputs/grpo_qwen_sql",
        per_device_train_batch_size=2,
        num_generations=4,
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=openenv_reward_func,
        args=training_args,
        train_dataset=train_dataset,
    )
    trainer.train()


if __name__ == "__main__":
    main()
