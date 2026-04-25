"""Prompt formatter for turning environment observations into chat messages."""

import json
from typing import Any

try:
    from ..models import SQLObservation
except ImportError:
    from models import SQLObservation


class TaskAgentFormatter:
    """Convert SQL observations into strict LLM-ready chat prompts."""

    SYSTEM_PROMPT = (
        "You are an autonomous Database Reliability Engineer. Your goal is to "
        "optimize slow PostgreSQL queries and fix schema issues. You MUST respond "
        "ONLY with a valid JSON object matching exactly one of the allowed action "
        "schemas. Do not include markdown code blocks (like ```json), "
        "conversational text, or explanations."
    )

    def format_observation(self, obs: SQLObservation) -> list[dict]:
        """Format observation into a standard system/user chat template."""
        metadata = self._to_dict(getattr(obs, "metadata", {}) or {})
        info = self._to_dict(metadata.get("info", {}) or {})

        baseline_execution_time_ms = getattr(obs, "execution_time_ms", None)
        if baseline_execution_time_ms is None:
            baseline_execution_time_ms = info.get(
                "initial_execution_time_ms",
                info.get("new_execution_time_ms", "unknown"),
            )

        plan = getattr(obs, "plan", None)
        if plan is None:
            plan = info.get("initial_plan", info.get("new_plan", {}))
        plan_json = json.dumps(plan, ensure_ascii=True, separators=(",", ":"))

        schema_diff = list(getattr(obs, "schema_diff", []) or [])
        if schema_diff:
            schema_drift_alerts = "\n".join(f"- {item}" for item in schema_diff)
        else:
            schema_drift_alerts = "- None"

        user_message = (
            f"Task ID: {obs.task_id}\n"
            f"Broken Query:\n{obs.broken_query}\n\n"
            f"Baseline Execution Time: {baseline_execution_time_ms} ms\n\n"
            f"PostgreSQL Execution Plan (JSON):\n{plan_json}\n\n"
            f"Schema Drift Alerts:\n{schema_drift_alerts}\n\n"
            "Respond with EXACTLY one JSON object in one of these formats:\n"
            '{"action_type":"rewrite_query","new_sql":"<rewritten_sql>"}\n'
            '{"action_type":"create_index","table_name":"<table_name>","column_name":"<column_name>"}'
        )

        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

    @staticmethod
    def _to_dict(value: Any) -> dict:
        """Best-effort conversion of pydantic/observation objects to dict."""
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            dumped = value.model_dump()
            if isinstance(dumped, dict):
                return dumped
        return {}
