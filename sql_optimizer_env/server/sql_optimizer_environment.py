"""SQL Query Optimizer Environment for OpenEnv — Meta PyTorch Hackathon.

An RL environment where an LLM agent must fix broken SQL queries and optimize
slow queries against a PostgreSQL e-commerce database. Supports three difficulty
levels (easy/medium/hard) with programmatic graders and multi-step episodes.
"""

import json
import os
import random
import re
from typing import Any, Optional, List, Tuple
from uuid import uuid4

import psycopg2
import psycopg2.extras
from pydantic import ValidationError

try:
    from openenv.core.env_server.interfaces import Environment
    from openenv.core.env_server.types import State
except ImportError:
    from openenv.core.env_server.interfaces import Environment
    from openenv.core.env_server.types import State

try:
    from ..models import (
        AgentAction,
        CreateIndexAction,
        RewriteQueryAction,
        SQLObservation,
        SQLReward,
    )
    from ..env.workload_generator import WorkloadGenerator
    from ..env.schema_drift import SchemaDrifter
    from ..env.rewards import calculate_all_rewards
except ImportError:
    from models import (
        AgentAction,
        CreateIndexAction,
        RewriteQueryAction,
        SQLObservation,
        SQLReward,
    )
    from env.workload_generator import WorkloadGenerator
    from env.schema_drift import SchemaDrifter
    from env.rewards import calculate_all_rewards

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin:admin@localhost:5432/dbre_env"
)

TABLES = {
    "customers": """CREATE TABLE IF NOT EXISTS customers (
        customer_id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        city TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""",
    "products": """CREATE TABLE IF NOT EXISTS products (
        product_id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price NUMERIC(10,2) NOT NULL,
        stock INTEGER DEFAULT 0
    )""",
    "orders": """CREATE TABLE IF NOT EXISTS orders (
        order_id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
        order_date TIMESTAMP DEFAULT NOW(),
        status TEXT DEFAULT 'pending'
    )""",
    "order_items": """CREATE TABLE IF NOT EXISTS order_items (
        item_id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(order_id),
        product_id INTEGER NOT NULL REFERENCES products(product_id),
        quantity INTEGER NOT NULL,
        unit_price NUMERIC(10,2) NOT NULL
    )""",
    "reviews": """CREATE TABLE IF NOT EXISTS reviews (
        review_id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
        product_id INTEGER NOT NULL REFERENCES products(product_id),
        rating INTEGER CHECK(rating BETWEEN 1 AND 5),
        review_text TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""",
}

SCHEMA_DESCRIPTION = """Tables:
- customers(customer_id, name, email, city, created_at)
- products(product_id, name, category, price, stock)
- orders(order_id, customer_id, order_date, status)
- order_items(item_id, order_id, product_id, quantity, unit_price)
- reviews(review_id, customer_id, product_id, rating, review_text, created_at)"""

TASKS = {
    "easy_fix_select": {
        "max_attempts": 5,
        "broken_query": "SELECT custmer_id, nm, emaill FROM customers WHERE city = 'Mumbai'",
        "expected_query": "SELECT customer_id, name, email FROM customers WHERE city = 'Mumbai'",
        "score_formula": lambda c, e, v: 0.5 * c + 0.3 * e + 0.2 * float(v),
    },
    "medium_slow_join": {
        "max_attempts": 7,
        "broken_query": "SELECT customers.name, orders.order_id, orders.status FROM customers, orders WHERE orders.status = 'completed'",
        "expected_query": "SELECT customers.name, orders.order_id, orders.status FROM customers JOIN orders ON customers.customer_id = orders.customer_id WHERE orders.status = 'completed'",
        "score_formula": lambda c, e, v: 0.5 * c + 0.3 * e + 0.2 * float(v),
    },
    "hard_subquery_optimize": {
        "max_attempts": 10,
        "broken_query": "SELECT customer_id, name, (SELECT COUNT(*) FROM orders WHERE orders.customer_id = customers.customer_id) as order_count, (SELECT SUM(unit_price * quantity) FROM order_items JOIN orders ON order_items.order_id = orders.order_id WHERE orders.customer_id = customers.customer_id) as total_spent FROM customers WHERE (SELECT COUNT(*) FROM orders WHERE orders.customer_id = customers.customer_id) > 2",
        "expected_query": "WITH customer_stats AS (SELECT o.customer_id, COUNT(o.order_id) as order_count, SUM(oi.unit_price * oi.quantity) as total_spent FROM orders o JOIN order_items oi ON o.order_id = oi.order_id GROUP BY o.customer_id) SELECT c.customer_id, c.name, cs.order_count, cs.total_spent FROM customers c JOIN customer_stats cs ON c.customer_id = cs.customer_id WHERE cs.order_count > 2",
        "score_formula": lambda c, e, v, u: min(
            1.0, 0.4 * c + 0.4 * e + 0.1 * float(v) + 0.1 * float(u)
        ),
    },
}

DESTRUCTIVE_RE = re.compile(
    r"\b(DROP|DELETE|TRUNCATE|ALTER|ATTACH|DETACH|REINDEX|VACUUM)\b", re.IGNORECASE
)
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _explain_analyze_json(conn, query: str) -> dict:
    """Run EXPLAIN (ANALYZE, FORMAT JSON) and return parsed plan + execution time.

    Returns dict with keys:
        execution_time_ms: float — total execution time in milliseconds
        plan: dict — the root plan node from PostgreSQL's EXPLAIN output
        total_cost: float — the planner's estimated total cost
    Falls back to sentinel values on error.
    """
    try:
        cur = conn.cursor()
        cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {query}")
        rows = cur.fetchall()
        conn.commit()
    except psycopg2.Error:
        conn.rollback()
        return {"execution_time_ms": 99999.0, "plan": {}, "total_cost": 99999.0}

    if not rows or not rows[0] or not rows[0][0]:
        return {"execution_time_ms": 99999.0, "plan": {}, "total_cost": 99999.0}

    explain_output = rows[0][0]
    if isinstance(explain_output, str):
        explain_output = json.loads(explain_output)

    root = explain_output[0] if isinstance(explain_output, list) else explain_output
    plan = root.get("Plan", {})
    execution_time = root.get("Execution Time", 99999.0)
    total_cost = plan.get("Total Cost", 99999.0)

    return {
        "execution_time_ms": execution_time,
        "plan": plan,
        "total_cost": total_cost,
    }


def _seed_data(conn) -> None:
    """Bulk-generate e-commerce data using PostgreSQL generate_series() and random().

    Produces 10k customers, 5k products, 100k orders, 500k order_items, 50k reviews.
    All generated server-side in raw SQL — no Python loops.
    """
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO customers (name, email, city)
        SELECT
            'Customer_' || gs,
            'cust' || gs || '@example.com',
            (ARRAY['Mumbai','Delhi','Bangalore','Chennai',
                   'Kolkata','Hyderabad','Pune','Ahmedabad'])
                [1 + floor(random() * 8)::int]
        FROM generate_series(1, 10000) AS gs
    """)

    cur.execute("""
        INSERT INTO products (name, category, price, stock)
        SELECT
            'Product_' || gs,
            (ARRAY['Electronics','Clothing','Books','Home','Sports'])
                [1 + floor(random() * 5)::int],
            round((5 + random() * 495)::numeric, 2),
            floor(random() * 201)::int
        FROM generate_series(1, 5000) AS gs
    """)

    cur.execute("""
        INSERT INTO orders (customer_id, order_date, status)
        SELECT
            1 + floor(random() * 10000)::int,
            DATE '2024-01-01' + (floor(random() * 365)::int || ' days')::interval,
            (ARRAY['pending','completed','shipped','cancelled'])
                [1 + floor(random() * 4)::int]
        FROM generate_series(1, 100000) AS gs
    """)

    cur.execute("""
        INSERT INTO order_items (order_id, product_id, quantity, unit_price)
        SELECT
            1 + floor(random() * 100000)::int,
            1 + floor(random() * 5000)::int,
            1 + floor(random() * 10)::int,
            round((5 + random() * 195)::numeric, 2)
        FROM generate_series(1, 500000) AS gs
    """)

    cur.execute("""
        INSERT INTO reviews (customer_id, product_id, rating, review_text)
        SELECT
            1 + floor(random() * 10000)::int,
            1 + floor(random() * 5000)::int,
            1 + floor(random() * 5)::int,
            (ARRAY['Great product!','Not bad','Could be better',
                   'Excellent','Terrible quality'])
                [1 + floor(random() * 5)::int]
        FROM generate_series(1, 50000) AS gs
    """)

    conn.commit()


class SQLOptimizerEnvironment(Environment):
    """OpenEnv environment for SQL query fixing and optimization.

    Manages a PostgreSQL e-commerce database with three graded tasks:
    - easy_fix_select: Correct wrong column names and missing conditions
    - medium_slow_join: Replace cartesian products with proper JOINs
    - hard_subquery_optimize: Rewrite nested subqueries using CTEs/window functions

    Each episode allows multiple attempts until the agent scores >= 0.95
    or exhausts max attempts. Indices created during attempts are dropped
    after each step to maintain statelessness.
    """

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        super().__init__()
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._conn = None
        self._current_task_id: Optional[str] = None
        self._attempts: int = 0
        self._max_attempts: int = 5
        self._current_score: float = 0.0
        self._previous_score: float = 0.0
        self._created_indices: List[str] = []

    def _setup_database(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = psycopg2.connect(DATABASE_URL)
        self._conn.autocommit = False
        cur = self._conn.cursor()
        cur.execute("DROP SCHEMA public CASCADE")
        cur.execute("CREATE SCHEMA public")
        self._conn.commit()
        for ddl in TABLES.values():
            cur.execute(ddl)
        self._conn.commit()
        _seed_data(self._conn)

    def _drop_created_indices(self) -> None:
        if not self._conn:
            return
        cur = self._conn.cursor()
        for idx_name in self._created_indices:
            try:
                cur.execute(f"DROP INDEX IF EXISTS {idx_name}")
            except psycopg2.Error:
                self._conn.rollback()
        self._conn.commit()
        self._created_indices = []

    def _verify_semantic_equivalence(
        self, cursor, expected_query: str, submitted_query: str
    ) -> Tuple[bool, Any, Any]:
        try:
            cursor.execute(expected_query)
            expected_rows = cursor.fetchall()
        except psycopg2.Error:
            self._conn.rollback()
            return False, None, None
        try:
            cursor.execute(submitted_query)
            submitted_rows = cursor.fetchall()
        except psycopg2.Error:
            self._conn.rollback()
            return False, expected_rows, None
        return expected_rows == submitted_rows, expected_rows, submitted_rows

    def _get_task(self, task_id: str) -> dict:
        return TASKS[task_id]

    def _is_destructive(self, query: str) -> bool:
        return bool(DESTRUCTIVE_RE.search(query))

    def _has_cte_or_window(self, query: str) -> bool:
        upper = query.upper()
        return (
            "WITH " in upper or "OVER(" in upper.replace(" ", "") or "OVER (" in upper
        )

    def reset(
        self,
        task_id: Optional[str] = None,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        use_workload_generator: bool = False,
        **kwargs: Any,
    ) -> SQLObservation:
        if seed is not None:
            random.seed(seed)
        self._drop_created_indices()
        self._setup_database()
        schema_diff: List[str] = []

        # Inject controlled schema chaos in 20% of episodes.
        if random.random() < 0.2:
            try:
                drifter = SchemaDrifter(seed=seed)
                drift_action = drifter.trigger_random_drift()
                schema_diff.append(drift_action)
            except Exception as exc:
                schema_diff.append(f"Schema drift failed: {exc}")

        if use_workload_generator or task_id is None:
            generator = WorkloadGenerator(seed=seed)
            task = generator.generate_slow_query()
            task_id = task["task_id"]
        else:
            task = self._get_task(task_id)

        self._current_task_id = task_id
        self._attempts = 0
        self._max_attempts = task["max_attempts"]
        self._current_score = 0.0
        self._previous_score = 0.0
        self._state = State(episode_id=episode_id or str(uuid4()), step_count=0)
        return SQLObservation(
            task_id=task_id,
            schema_description=SCHEMA_DESCRIPTION,
            broken_query=task["broken_query"],
            error_message=None,
            current_score=0.0,
            attempts=0,
            max_attempts=self._max_attempts,
            done=False,
            reward=0.01,
            schema_diff=schema_diff,
            metadata={"status": "ready", "schema_diff_applied": bool(schema_diff)},
        )

    def step(
        self, action: AgentAction, timeout_s: Optional[float] = None, **kwargs: Any
    ) -> SQLObservation:
        self._state.step_count += 1
        self._attempts += 1

        if not self._conn or not self._current_task_id:
            return SQLObservation(
                task_id="",
                schema_description="",
                broken_query="",
                error_message="Environment not initialized. Call reset() first.",
                current_score=self._current_score,
                attempts=self._attempts,
                max_attempts=self._max_attempts,
                done=True,
                reward=0.01,
                metadata={"error": "not_initialized"},
            )

        task = self._get_task(self._current_task_id)
        schema_diff: List[str] = []
        parsed_action: AgentAction
        try:
            if isinstance(action, RewriteQueryAction | CreateIndexAction):
                parsed_action = action
            elif isinstance(action, dict):
                action_type = action.get("action_type")
                if action_type == "rewrite_query":
                    parsed_action = RewriteQueryAction(**action)
                elif action_type == "create_index":
                    parsed_action = CreateIndexAction(**action)
                else:
                    raise ValueError(
                        "Invalid action_type. Expected 'rewrite_query' or 'create_index'."
                    )
            else:
                parsed_action = RewriteQueryAction(**action.model_dump())
        except (ValidationError, ValueError, AttributeError) as exc:
            return SQLObservation(
                task_id=self._current_task_id,
                schema_description=SCHEMA_DESCRIPTION,
                broken_query=task["broken_query"],
                error_message=f"Invalid action payload: {exc}",
                current_score=self._current_score,
                attempts=self._attempts,
                max_attempts=self._max_attempts,
                done=False,
                reward=-1.0,
                schema_diff=schema_diff,
                metadata={"error": "invalid_action"},
            )

        statements: List[str]
        evaluation_query: str
        action_payload: dict[str, str]
        if isinstance(parsed_action, RewriteQueryAction):
            submitted_query = parsed_action.new_sql.strip()
            statements = [s.strip() for s in submitted_query.split(";") if s.strip()]
            evaluation_query = submitted_query
            action_payload = {"query": submitted_query}
        else:
            table_name = parsed_action.table_name.strip()
            column_name = parsed_action.column_name.strip()
            if not IDENTIFIER_RE.match(table_name) or not IDENTIFIER_RE.match(column_name):
                return SQLObservation(
                    task_id=self._current_task_id,
                    schema_description=SCHEMA_DESCRIPTION,
                    broken_query=task["broken_query"],
                    error_message="Unsafe identifier in create_index action.",
                    current_score=self._current_score,
                    attempts=self._attempts,
                    max_attempts=self._max_attempts,
                    done=False,
                    reward=-1.0,
                    schema_diff=schema_diff,
                    metadata={"error": "invalid_identifier"},
                )
            index_name = f"idx_{table_name}_{column_name}_{self._attempts}"
            create_index_sql = (
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
            )
            statements = [create_index_sql]
            evaluation_query = task["broken_query"]
            action_payload = {"query": create_index_sql}
            schema_diff.append(create_index_sql)
            self._created_indices.append(index_name)
            submitted_query = create_index_sql

        if self._is_destructive(submitted_query):
            self._current_score = 0.0
            final_value = -5.0
            return SQLObservation(
                task_id=self._current_task_id,
                schema_description=SCHEMA_DESCRIPTION,
                broken_query=task["broken_query"],
                error_message="Destructive query detected.",
                current_score=0.0,
                attempts=self._attempts,
                max_attempts=self._max_attempts,
                done=True,
                reward=final_value,
                schema_diff=schema_diff,
                metadata={
                    "value": final_value,
                    "correctness": -1.0,
                    "efficiency": 0.0,
                    "style": 0.0,
                    "anticheat": -5.0,
                    "done": True,
                    "info": {"destructive": True},
                },
            )

        is_valid_sql = True
        execution_error = None

        for stmt in statements:
            try:
                cur = self._conn.cursor()
                cur.execute(stmt)
                if cur.description is not None:
                    cur.fetchall()
                match = re.search(
                    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
                    stmt,
                    re.IGNORECASE,
                )
                if match:
                    self._created_indices.append(match.group(1))
                self._conn.commit()
            except psycopg2.Error as e:
                self._conn.rollback()
                is_valid_sql = False
                execution_error = str(e).strip()
                break

        if not is_valid_sql:
            self._drop_created_indices()
            done = self._attempts >= self._max_attempts
            baseline_trace = _explain_analyze_json(self._conn, task["broken_query"])
            failed_trace = {
                "execution_time_ms": 99999.0,
                "plan": {},
                "total_cost": 99999.0,
            }
            try:
                rewards = calculate_all_rewards(
                    baseline_trace=baseline_trace,
                    new_trace=failed_trace,
                    action_taken=action_payload,
                    results_match=False,
                )
                final_value = rewards["total"]
                reward_errors = None
            except Exception as exc:
                final_value = -1.0
                rewards = {
                    "correctness": -1.0,
                    "efficiency": -1.0,
                    "style": 0.0,
                    "anticheat": 0.0,
                    "total": final_value,
                }
                reward_errors = str(exc)
            self._current_score = final_value
            return SQLObservation(
                task_id=self._current_task_id,
                schema_description=SCHEMA_DESCRIPTION,
                broken_query=task["broken_query"],
                error_message=execution_error,
                current_score=self._current_score,
                attempts=self._attempts,
                max_attempts=self._max_attempts,
                done=done,
                reward=final_value,
                metadata={
                    "value": final_value,
                    "correctness": rewards["correctness"],
                    "efficiency": rewards["efficiency"],
                    "style": rewards["style"],
                    "anticheat": rewards["anticheat"],
                    "is_valid_sql": False,
                    "done": done,
                    "info": {
                        "reward_errors": reward_errors,
                    },
                },
                schema_diff=schema_diff,
            )

        cur = self._conn.cursor()
        semantic_match, _, _ = self._verify_semantic_equivalence(
            cur, task["expected_query"], evaluation_query
        )

        initial_explain = _explain_analyze_json(self._conn, task["broken_query"])
        new_explain = _explain_analyze_json(self._conn, evaluation_query)
        try:
            rewards = calculate_all_rewards(
                baseline_trace=initial_explain,
                new_trace=new_explain,
                action_taken=action_payload,
                results_match=semantic_match,
            )
            reward_errors = None
        except Exception as exc:
            rewards = {
                "correctness": 1.0 if semantic_match else -1.0,
                "efficiency": 0.0,
                "style": 0.0,
                "anticheat": 0.0,
                "total": -1.0 if not semantic_match else 0.0,
            }
            reward_errors = str(exc)

        final_value = rewards["total"]
        self._previous_score = self._current_score
        self._current_score = final_value

        done = self._attempts >= self._max_attempts or rewards["correctness"] >= 1.0
        self._drop_created_indices()

        return SQLObservation(
            task_id=self._current_task_id,
            schema_description=SCHEMA_DESCRIPTION,
            broken_query=task["broken_query"],
            error_message=None,
            current_score=self._current_score,
            attempts=self._attempts,
            max_attempts=self._max_attempts,
            done=done,
            reward=final_value,
            schema_diff=schema_diff,
            metadata={
                "value": final_value,
                "correctness": rewards["correctness"],
                "efficiency": rewards["efficiency"],
                "style": rewards["style"],
                "anticheat": rewards["anticheat"],
                "is_valid_sql": is_valid_sql,
                "done": done,
                "info": {
                    "initial_execution_time_ms": initial_explain["execution_time_ms"],
                    "new_execution_time_ms": new_explain["execution_time_ms"],
                    "initial_cost": initial_explain["total_cost"],
                    "new_cost": new_explain["total_cost"],
                    "initial_plan": initial_explain["plan"],
                    "new_plan": new_explain["plan"],
                    "semantic_match": semantic_match,
                    "uses_cte_or_window": self._has_cte_or_window(evaluation_query),
                    "action_type": parsed_action.action_type,
                    "reward_errors": reward_errors,
                },
            },
        )

    @property
    def state(self) -> State:
        return self._state

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
