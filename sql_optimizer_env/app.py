"""Gradio demo dashboard for the Autonomic DBRE agent (Space entrypoint)."""

from __future__ import annotations

import difflib
import json
from typing import Any

import gradio as gr

from models import RewriteQueryAction
from server.sql_optimizer_environment import SQLOptimizerEnvironment, _explain_analyze_json


def _dummy_agent_inference(broken_query: str) -> RewriteQueryAction:
    query = " ".join(broken_query.split())
    upper = query.upper()
    if "FROM CUSTOMERS, ORDERS" in upper and "WHERE ORDERS.STATUS" in upper:
        fixed = (
            "SELECT customers.name, orders.order_id, orders.status "
            "FROM customers JOIN orders ON customers.customer_id = orders.customer_id "
            "WHERE orders.status = 'completed'"
        )
    elif "IN (SELECT" in upper and "JOIN" not in upper:
        fixed = (
            "SELECT DISTINCT c.customer_id, c.name FROM customers c "
            "JOIN reviews r ON c.customer_id = r.customer_id WHERE r.rating >= 4"
        )
    else:
        fixed = query
    return RewriteQueryAction(action_type="rewrite_query", new_sql=fixed)


def _format_schema_alerts(alerts: list[str]) -> str:
    if not alerts:
        return "No schema drift detected."
    return "\n".join(f"- {alert}" for alert in alerts)


def _format_sql_diff(original: str, updated: str) -> str:
    diff = difflib.unified_diff(
        original.splitlines(),
        updated.splitlines(),
        fromfile="broken.sql",
        tofile="agent_fix.sql",
        lineterm="",
    )
    text = "\n".join(diff)
    return text if text.strip() else "No textual SQL changes detected."


def run_demo_episode() -> tuple[str, str, str, str, str, str, str]:
    env = SQLOptimizerEnvironment()
    try:
        obs = env.reset(use_workload_generator=True)
        broken_query = obs.broken_query
        schema_alerts = _format_schema_alerts(obs.schema_diff)

        baseline_trace = _explain_analyze_json(env._conn, broken_query)  # type: ignore[attr-defined]
        baseline_ms = float(baseline_trace.get("execution_time_ms", 0.0))

        action = _dummy_agent_inference(broken_query)
        step_obs = env.step(action)

        metadata: dict[str, Any] = step_obs.metadata or {}
        info: dict[str, Any] = metadata.get("info", {}) or {}
        new_ms = float(info.get("new_execution_time_ms", baseline_ms))

        reward_breakdown = {
            "correctness": float(metadata.get("correctness", 0.0)),
            "efficiency": float(metadata.get("efficiency", 0.0)),
            "style": float(metadata.get("style", 0.0)),
            "anticheat": float(metadata.get("anticheat", 0.0)),
            "total": float(metadata.get("value", step_obs.reward)),
        }

        return (
            broken_query,
            schema_alerts,
            f"<span style='color:#ff4d4f;font-weight:700'>{baseline_ms:.2f} ms</span>",
            action.new_sql,
            f"<span style='color:#22c55e;font-weight:700'>{new_ms:.2f} ms</span>",
            json.dumps(reward_breakdown, indent=2),
            _format_sql_diff(broken_query, action.new_sql),
        )
    except Exception as exc:
        error = f"Demo episode failed: {exc}"
        return error, error, error, error, error, error, error
    finally:
        env.close()


with gr.Blocks(theme=gr.Theme.from_hub("gradio/monochrome")) as demo:
    gr.Markdown("# 🧠 Autonomic DBRE: Self-Healing Database Agent")
    run_button = gr.Button("Inject Database Chaos & Run Agent", variant="primary", size="lg")

    with gr.Row():
        with gr.Column():
            gr.Markdown("## The Problem")
            slow_query = gr.Code(label="Injected Slow Query", language="sql")
            schema_alerts = gr.Markdown(label="Schema Drift Alerts")
            baseline_latency = gr.Markdown(label="Baseline Latency")
        with gr.Column():
            gr.Markdown("## The Solution")
            generated_sql = gr.Code(label="Agent SQL Fix", language="sql")
            new_latency = gr.Markdown(label="Optimized Latency")
            reward_breakdown = gr.Code(label="Multi-Dimensional Reward", language="json")

    sql_diff = gr.Textbox(label="SQL Diff", lines=10)
    run_button.click(
        fn=run_demo_episode,
        inputs=[],
        outputs=[
            slow_query,
            schema_alerts,
            baseline_latency,
            generated_sql,
            new_latency,
            reward_breakdown,
            sql_diff,
        ],
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
