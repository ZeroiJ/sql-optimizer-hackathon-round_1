from openenv.core.env_client import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

try:
    from .models import AgentAction, CreateIndexAction, RewriteQueryAction, SQLObservation
except ImportError:
    from models import AgentAction, CreateIndexAction, RewriteQueryAction, SQLObservation


class SQLOptimizerEnv(EnvClient[AgentAction, SQLObservation, State]):
    def _step_payload(self, action: AgentAction) -> dict:
        if isinstance(action, RewriteQueryAction):
            return {"action_type": "rewrite_query", "new_sql": action.new_sql}
        if isinstance(action, CreateIndexAction):
            return {
                "action_type": "create_index",
                "table_name": action.table_name,
                "column_name": action.column_name,
            }
        raise ValueError("Unsupported action type for payload serialization.")

    def _parse_result(self, payload: dict) -> StepResult[SQLObservation]:
        obs_data = payload.get("observation", {})
        obs = SQLObservation(
            task_id=obs_data.get("task_id", ""),
            schema_description=obs_data.get("schema_description", ""),
            broken_query=obs_data.get("broken_query", ""),
            error_message=obs_data.get("error_message"),
            current_score=obs_data.get("current_score", 0.0),
            attempts=obs_data.get("attempts", 0),
            max_attempts=obs_data.get("max_attempts", 5),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )
        return StepResult(
            observation=obs,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
