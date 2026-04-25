"""Pydantic models for the SQL Query Optimizer RL Environment."""

from typing import Optional, Dict, Any, Union, Annotated, Literal
from pydantic import Field

try:
    from openenv.core.env_server.types import Action, Observation
except ImportError:
    from openenv.core.env_server.types import Action, Observation


class RewriteQueryAction(Action):
    """Action to rewrite and submit a full SQL query."""

    action_type: Literal["rewrite_query"] = Field(
        ..., description="Discriminator for rewrite query actions"
    )
    new_sql: str = Field(..., description="The rewritten SQL query to execute")


class CreateIndexAction(Action):
    """Action to create an index for optimization."""

    action_type: Literal["create_index"] = Field(
        ..., description="Discriminator for create index actions"
    )
    table_name: str = Field(..., description="Target table name for index creation")
    column_name: str = Field(..., description="Target column name for index creation")


AgentAction = Annotated[
    Union[RewriteQueryAction, CreateIndexAction],
    Field(discriminator="action_type"),
]


class SQLObservation(Observation):
    """Observation containing task context and schema information."""

    task_id: str = Field(..., description="Which task is active (e.g. easy_fix_select)")
    schema_description: str = Field(..., description="Human-readable schema summary")
    broken_query: str = Field(
        ..., description="The broken/inefficient query the agent needs to fix"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error if last submission failed, else None"
    )
    current_score: float = Field(
        default=0.0, description="Running score for this episode (0.0 - 1.0)"
    )
    attempts: int = Field(default=0, description="How many attempts agent has made")
    max_attempts: int = Field(
        default=5, description="Max attempts allowed for this task"
    )
    schema_diff: list[str] = Field(
        default_factory=list,
        description="Schema drift/index changes applied in the current episode",
    )


class SQLReward:
    """Reward returned after each step."""

    def __init__(
        self,
        value: float = 0.0,
        correctness: float = 0.0,
        efficiency: float = 0.0,
        is_valid_sql: bool = True,
        done: bool = False,
        info: Optional[Dict[str, Any]] = None,
    ):
        self.value = value
        self.correctness = correctness
        self.efficiency = efficiency
        self.is_valid_sql = is_valid_sql
        self.done = done
        self.info = info or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "correctness": self.correctness,
            "efficiency": self.efficiency,
            "is_valid_sql": self.is_valid_sql,
            "done": self.done,
            "info": self.info,
        }
