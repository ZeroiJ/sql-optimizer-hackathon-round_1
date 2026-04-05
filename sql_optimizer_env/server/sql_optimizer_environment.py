"""SQL Query Optimizer Environment for OpenEnv — Meta PyTorch Hackathon.

An RL environment where an LLM agent must fix broken SQL queries and optimize
slow queries against a SQLite e-commerce database. Supports three difficulty
levels (easy/medium/hard) with programmatic graders and multi-step episodes.
"""

import random
import re
import sqlite3
from typing import Any, Optional, List, Tuple
from uuid import uuid4

try:
    from openenv.core.env_server.interfaces import Environment
    from openenv.core.env_server.types import State
except ImportError:
    from openenv.core.env_server.interfaces import Environment
    from openenv.core.env_server.types import State

try:
    from ..models import SQLAction, SQLObservation, SQLReward
except ImportError:
    from models import SQLAction, SQLObservation, SQLReward

TABLES = {
    "customers": """CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        city TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    "products": """CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER DEFAULT 0
    )""",
    "orders": """CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        order_date TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    )""",
    "order_items": """CREATE TABLE order_items (
        item_id INTEGER PRIMARY KEY,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    )""",
    "reviews": """CREATE TABLE reviews (
        review_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        rating INTEGER CHECK(rating BETWEEN 1 AND 5),
        review_text TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
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


def _calculate_query_cost(conn: sqlite3.Connection, query: str) -> float:
    """Estimate query execution cost via EXPLAIN QUERY PLAN heuristics.

    Args:
        conn: Active SQLite connection.
        query: SQL query to analyze.

    Returns:
        Numeric cost score. Lower is better. Returns 10000.0 on parse error.
    """
    try:
        cursor = conn.cursor()
        cursor.execute(f"EXPLAIN QUERY PLAN {query}")
        rows = cursor.fetchall()
    except sqlite3.Error:
        return 10000.0
    if not rows:
        return 0.0
    cost = 0.0
    for row in rows:
        detail = row[-1].upper() if row[-1] else ""
        if "SCAN " in detail:
            cost += 100.0
        if "SEARCH " in detail:
            cost += 10.0
        if "USE TEMP B-TREE" in detail:
            cost += 50.0
        if "AUTOMATIC INDEX" in detail:
            cost += 75.0
        if "CORRELATED SCALAR SUBQUERY" in detail:
            cost += 150.0
        if "COVERING INDEX" in detail:
            cost -= 20.0
    return cost


def _seed_data(conn: sqlite3.Connection) -> None:
    """Populate all five tables with deterministic mock e-commerce data.

    Uses random.seed(42) for reproducibility. Inserts ~100 customers, ~50 products,
    ~300 orders, ~600 order items, and ~200 reviews.

    Args:
        conn: Active SQLite connection with schema already created.
    """
    random.seed(42)
    cur = conn.cursor()
    cities = [
        "Mumbai",
        "Delhi",
        "Bangalore",
        "Chennai",
        "Kolkata",
        "Hyderabad",
        "Pune",
        "Ahmedabad",
    ]
    categories = ["Electronics", "Clothing", "Books", "Home", "Sports"]
    statuses = ["pending", "completed", "shipped", "cancelled"]
    review_texts = [
        "Great product!",
        "Not bad",
        "Could be better",
        "Excellent",
        "Terrible quality",
    ]
    for i in range(100):
        cur.execute(
            "INSERT INTO customers (name, email, city) VALUES (?, ?, ?)",
            (f"Customer_{i}", f"cust{i}@example.com", random.choice(cities)),
        )
    for i in range(50):
        cur.execute(
            "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
            (
                f"Product_{i}",
                random.choice(categories),
                round(random.uniform(5, 500), 2),
                random.randint(0, 200),
            ),
        )
    for i in range(300):
        cur.execute(
            "INSERT INTO orders (customer_id, order_date, status) VALUES (?, ?, ?)",
            (
                random.randint(1, 100),
                f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                random.choice(statuses),
            ),
        )
    for i in range(600):
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
            (
                random.randint(1, 300),
                random.randint(1, 50),
                random.randint(1, 10),
                round(random.uniform(5, 200), 2),
            ),
        )
    for i in range(200):
        cur.execute(
            "INSERT INTO reviews (customer_id, product_id, rating, review_text) VALUES (?, ?, ?, ?)",
            (
                random.randint(1, 100),
                random.randint(1, 50),
                random.randint(1, 5),
                random.choice(review_texts),
            ),
        )
    conn.commit()


class SQLOptimizerEnvironment(Environment):
    """OpenEnv environment for SQL query fixing and optimization.

    Manages a SQLite e-commerce database with three graded tasks:
    - easy_fix_select: Correct wrong column names and missing conditions
    - medium_slow_join: Replace cartesian products with proper JOINs
    - hard_subquery_optimize: Rewrite nested subqueries using CTEs/window functions

    Each episode allows multiple attempts until the agent scores >= 0.95
    or exhausts max attempts. Indices created during attempts are dropped
    after each step to maintain statelessness.
    """

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        """Initialize environment state with empty session variables."""
        super().__init__()
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._conn: Optional[sqlite3.Connection] = None
        self._current_task_id: Optional[str] = None
        self._attempts: int = 0
        self._max_attempts: int = 5
        self._current_score: float = 0.0
        self._previous_score: float = 0.0
        self._created_indices: List[str] = []

    def _setup_database(self) -> None:
        """Create fresh in-memory SQLite database with schema and seed data."""
        if self._conn:
            self._conn.close()
        self._conn = sqlite3.connect(":memory:")
        self._conn.execute("PRAGMA foreign_keys = ON")
        for ddl in TABLES.values():
            self._conn.execute(ddl)
        _seed_data(self._conn)
        self._conn.commit()

    def _drop_created_indices(self) -> None:
        """Drop all indices created during the current step to maintain statelessness."""
        if not self._conn:
            return
        cur = self._conn.cursor()
        for idx_name in self._created_indices:
            try:
                cur.execute(f"DROP INDEX IF EXISTS {idx_name}")
            except sqlite3.Error:
                pass
        self._conn.commit()
        self._created_indices = []

    def _verify_semantic_equivalence(
        self, cursor: sqlite3.Cursor, expected_query: str, submitted_query: str
    ) -> Tuple[bool, Any, Any]:
        """Compare result sets of expected and submitted queries for correctness grading.

        Args:
            cursor: SQLite cursor for executing queries.
            expected_query: Reference query producing the correct result set.
            submitted_query: Agent's submitted query to validate.

        Returns:
            Tuple of (is_match, expected_rows, submitted_rows).
        """
        try:
            cursor.execute(expected_query)
            expected_rows = cursor.fetchall()
        except sqlite3.Error:
            return False, None, None
        try:
            cursor.execute(submitted_query)
            submitted_rows = cursor.fetchall()
        except sqlite3.Error:
            return False, expected_rows, None
        return expected_rows == submitted_rows, expected_rows, submitted_rows

    def _get_task(self, task_id: str) -> dict:
        """Return task configuration dict for the given task_id.

        Args:
            task_id: One of the keys in TASKS (easy_fix_select, medium_slow_join, hard_subquery_optimize).

        Returns:
            Dict with max_attempts, broken_query, expected_query, and score_formula.
        """
        return TASKS[task_id]

    def _is_destructive(self, query: str) -> bool:
        """Check if query contains destructive SQL keywords.

        Args:
            query: Raw SQL string to scan.

        Returns:
            True if query matches DROP, DELETE, TRUNCATE, ALTER, ATTACH, DETACH, REINDEX, or VACUUM.
        """
        return bool(DESTRUCTIVE_RE.search(query))

    def _has_cte_or_window(self, query: str) -> bool:
        """Detect whether query uses WITH (CTE) or window function syntax.

        Args:
            query: Raw SQL string to analyze.

        Returns:
            True if query contains WITH clause or OVER() window function.
        """
        upper = query.upper()
        return (
            "WITH " in upper or "OVER(" in upper.replace(" ", "") or "OVER (" in upper
        )

    def reset(
        self,
        task_id: Optional[str] = None,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> SQLObservation:
        """Reset the environment to a fresh database and return the initial observation.

        Creates a new in-memory SQLite database, seeds it with deterministic data,
        and selects a task (random if task_id is None). Resets attempt counters
        and drops any lingering indices.

        Args:
            task_id: Specific task to load. Random if None.
            seed: Random seed for reproducibility.
            episode_id: Custom episode identifier.

        Returns:
            SQLObservation with task context, broken query, and initial state.
        """
        if seed is not None:
            random.seed(seed)
        self._drop_created_indices()
        self._setup_database()
        if task_id is None:
            task_id = random.choice(list(TASKS.keys()))
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
            reward=0.0,
            metadata={"status": "ready"},
        )

    def step(
        self, action: SQLAction, timeout_s: Optional[float] = None, **kwargs: Any
    ) -> SQLObservation:
        """Execute the agent's query and return graded observation with reward.

        Validates the submitted query (destructive check, syntax check), executes
        it against the database, compares results against the expected query for
        semantic equivalence, calculates efficiency via EXPLAIN QUERY PLAN cost
        heuristics, and computes a composite score with improvement/speed bonuses.

        Args:
            action: Agent's SQLAction containing the submitted query.
            timeout_s: Optional timeout (not enforced in sync implementation).

        Returns:
            SQLObservation with updated score, reward, attempt count, and done flag.
        """
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
                reward=-0.1,
                metadata={"error": "not_initialized"},
            )

        task = self._get_task(self._current_task_id)
        # Defensive: handle both SQLAction and raw dict (deserialization may vary by deployment)
        if isinstance(action, dict):
            submitted_query = action.get("query", "").strip()
        else:
            submitted_query = action.query.strip()

        if self._is_destructive(submitted_query):
            self._current_score = 0.0
            return SQLObservation(
                task_id=self._current_task_id,
                schema_description=SCHEMA_DESCRIPTION,
                broken_query=task["broken_query"],
                error_message="Destructive query detected.",
                current_score=0.0,
                attempts=self._attempts,
                max_attempts=self._max_attempts,
                done=True,
                reward=-1.0,
                metadata={"destructive": True},
            )

        statements = [s.strip() for s in submitted_query.split(";") if s.strip()]
        is_valid_sql = True
        execution_error = None

        for stmt in statements:
            try:
                cur = self._conn.cursor()
                cur.execute(stmt)
                cur.fetchall()
                match = re.search(
                    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
                    stmt,
                    re.IGNORECASE,
                )
                if match:
                    self._created_indices.append(match.group(1))
            except sqlite3.Error as e:
                is_valid_sql = False
                execution_error = str(e)
                break

        self._conn.commit()

        if not is_valid_sql:
            self._drop_created_indices()
            done = self._attempts >= self._max_attempts
            return SQLObservation(
                task_id=self._current_task_id,
                schema_description=SCHEMA_DESCRIPTION,
                broken_query=task["broken_query"],
                error_message=execution_error,
                current_score=self._current_score,
                attempts=self._attempts,
                max_attempts=self._max_attempts,
                done=done,
                reward=-0.1,
                metadata={"is_valid_sql": False},
            )

        cur = self._conn.cursor()
        semantic_match, _, _ = self._verify_semantic_equivalence(
            cur, task["expected_query"], submitted_query
        )
        correctness = 1.0 if semantic_match else 0.0

        if not semantic_match and self._current_task_id == "easy_fix_select":
            try:
                cur.execute(submitted_query)
                rows = cur.fetchall()
                if rows and len(rows) > 0:
                    correctness = 0.2
            except sqlite3.Error:
                pass

        initial_cost = _calculate_query_cost(self._conn, task["broken_query"])
        new_cost = _calculate_query_cost(self._conn, submitted_query)

        if initial_cost > 0:
            efficiency = max(0.0, min(1.0, (initial_cost - new_cost) / initial_cost))
        else:
            efficiency = 1.0 if new_cost <= initial_cost else 0.0

        uses_cte = self._has_cte_or_window(submitted_query)
        formula = task["score_formula"]
        if self._current_task_id == "hard_subquery_optimize":
            base_score = formula(correctness, efficiency, is_valid_sql, uses_cte)
        else:
            base_score = formula(correctness, efficiency, is_valid_sql)

        improvement_bonus = max(0, base_score - self._previous_score) * 0.2
        attempt_ratio = self._attempts / self._max_attempts
        speed_bonus = 0.1 * (1 - attempt_ratio) if correctness == 1.0 else 0
        final_value = min(1.0, base_score + improvement_bonus + speed_bonus)
        self._current_score = final_value
        self._previous_score = base_score

        done = self._attempts >= self._max_attempts or final_value >= 0.95
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
            metadata={
                "value": final_value,
                "correctness": correctness,
                "efficiency": efficiency,
                "is_valid_sql": is_valid_sql,
                "done": done,
                "info": {
                    "initial_cost": initial_cost,
                    "new_cost": new_cost,
                    "semantic_match": semantic_match,
                    "uses_cte_or_window": uses_cte,
                    "improvement_bonus": improvement_bonus,
                    "speed_bonus": speed_bonus,
                },
            },
        )

    @property
    def state(self) -> State:
        """Return the current episode and step count."""
        return self._state

    def close(self) -> None:
        """Close the in-memory SQLite connection and release resources."""
        if self._conn:
            self._conn.close()
            self._conn = None
