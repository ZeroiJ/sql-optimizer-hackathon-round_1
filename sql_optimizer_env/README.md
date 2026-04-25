---
title: Autonomic DBRE
emoji: 🧠
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: "4.44.0"
python_version: "3.10"
app_file: app.py
pinned: false
---

# 🧠 Autonomic DBRE: The Self-Healing Database Agent

**Theme:** Self-Improving Agent Systems & Long-Horizon Planning
**Team:** Yash Balpande, Sujal Birwadkar, Smit Bhosale

## 1. The Problem: Databases Break in Production
Real databases fail in unpredictable ways. A query that executed in 10ms yesterday takes 5 seconds today because a table grew, traffic spiked, or a developer accidentally dropped an index. Traditional query optimizers are static. We built an agent that experiences database chaos, diagnoses the root cause via execution traces, applies fixes, and *learns* to handle novel schema degradation over time.

## 2. The Environment: Hostile PostgreSQL
Unlike static grid-worlds, our agent operates against a live, containerized PostgreSQL instance loaded with 500k+ rows of synthetic data. 

* **The Chaos Engine:** We implemented a `SchemaDrifter` that randomly degrades the database between episodes (dropping indexes, renaming columns, altering types).
* **Observation Space:** The agent receives the broken SQL query, the `EXPLAIN ANALYZE` JSON trace, baseline execution time, and schema drift alerts.
* **Action Space:** Strict Pydantic-validated actions to either `RewriteQuery` or `CreateIndex`.

## 3. The Multi-Dimensional Reward Matrix
We enforce strict behavior using a 4-signal reward system:
1. **Correctness (Binary):** Did the rewritten query return the exact same semantic results? (+1.0 / -1.0)
2. **Efficiency (Continuous):** Percentage reduction in execution time. (Up to +1.0)
3. **Style (Heuristic):** Penalty for lazy `SELECT *` or nested subqueries where joins exist. (+0.5)
4. **Anti-Cheat (Strict):** Massive penalty for destructive actions like `DROP TABLE`. (-5.0)

## 4. Training the Agent (Unsloth + GRPO)
Because 7B parameter models are heavy, we utilized **Unsloth 4-bit quantization with LoRA adapters** to fit the training loop into available compute. 

We trained our policy using **TRL's Group Relative Policy Optimization (GRPO)**. The model generates 4 candidate fixes per broken query, evaluates them all securely in the OpenEnv sandbox, and updates its weights based on relative reward advantages.

## 5. Try It Live
Click the "Inject Database Chaos" button in the UI above to watch the agent diagnose and repair a live PostgreSQL sequential scan in real-time.