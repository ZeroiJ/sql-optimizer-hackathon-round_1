# OpenEnv Hackathon — Rules, Requirements & Disqualification Criteria
> **Deadline: April 8th, 11:59 PM**
> Hosted by: Meta x Scaler | Tagged: `openenv` on HuggingFace Spaces

---

## THE TASK (Plain English)

Build a **real-world OpenEnv environment** that an AI agent can learn from using three standard API methods:

```python
env.step(action)   # Agent takes an action, env returns result
env.reset()        # Resets environment to initial state
env.state()        # Returns current state of the environment
```

This is NOT a game. It must simulate something a human actually does in the real world (e.g. fixing SQL queries, triaging emails, cleaning data).

**Our environment:** SQL Query Optimizer — agent receives a broken/slow SQL query and must fix/optimize it.

---

## FUNCTIONAL REQUIREMENTS (Must Have)

### 1. Real-World Task Simulation
- Must simulate a task **humans actually perform**
- Examples given by organizers: email triage, code review, data cleaning, scheduling, customer support, content moderation
- **NO games, NO toys**

### 2. Full OpenEnv Spec Compliance
You must implement the complete OpenEnv interface:

| Component | What it must do |
|-----------|----------------|
| `Observation` | Typed Pydantic model |
| `Action` | Typed Pydantic model |
| `Reward` | Typed Pydantic model |
| `step(action)` | Returns `(observation, reward, done, info)` |
| `reset()` | Returns initial observation |
| `state()` | Returns current environment state |
| `openenv.yaml` | Metadata file describing the environment |

- Must pass `openenv validate` — the official spec validator

### 3. Minimum 3 Tasks with Agent Graders
- Each task must have a **concrete objective** an agent must accomplish
- Each task must have a **programmatic grader** that scores 0.0 → 1.0
- Difficulty must range: **Easy → Medium → Hard**
- Graders must have **clear, deterministic success/failure criteria**
- No hardcoded or static scores — graders must actually evaluate the agent's output

**Our 3 tasks:**
- Easy — Fix a broken SELECT with WHERE/ORDER BY
- Medium — Rewrite a slow JOIN or aggregation query
- Hard — Optimize subqueries, CTEs, or window functions

### 4. Meaningful Reward Function
- Must provide signal over the **full trajectory**, not just at end of episode
- Must reward **partial progress** toward task completion
- Must **penalize clearly undesirable behavior** (e.g. infinite loops, destructive actions, dropping tables)
- Binary win/lose at the end is NOT enough

### 5. Baseline Inference Script
- Must use the **OpenAI API client** to run a model against the environment
- Must read API credentials from environment variable: `OPENAI_API_KEY`
- Must produce **reproducible baseline scores** on all 3 tasks
- Anyone running it should get the same (or very close) scores

---

## NON-FUNCTIONAL REQUIREMENTS (Infrastructure)

### 6. Deploy to HuggingFace Spaces
- Environment must run as a **containerized HF Space**
- Must be tagged with `openenv` on HuggingFace
- The space must **actually respond** when hit

### 7. Working Dockerfile
- Must include a working `Dockerfile`
- Environment must start cleanly with:
  ```bash
  docker build .
  docker run .
  ```
- No broken builds, no missing dependencies

### 8. README Documentation
README must include all of the following:
- Environment description and motivation (why does this exist?)
- Action space definition (what can the agent do?)
- Observation space definition (what does the agent see?)
- Task descriptions with expected difficulty levels
- Setup and usage instructions
- Baseline scores (what does a baseline agent score on each task?)

---

## JUDGING — How It Works

### Phase 1: Automated Validation (Pass/Fail Gate)
If you fail this, you're out. Period.

| Check | What they verify |
|-------|-----------------|
| HF Space deploys | Space is live and responds |
| OpenEnv spec compliance | Passes `openenv validate` |
| Dockerfile builds | `docker build` + `docker run` works |
| Baseline reproduces | Script runs and produces scores |
| 3+ tasks with graders | All tasks exist and grade correctly |

### Phase 2: Agentic Evaluation (Scored)
- Baseline agent is re-run against your environment
- A standard Open LLM agent (e.g. **Nemotron 3 Super**) is run against all environments
- Score variance is checked — graders must behave consistently

### Phase 3: Human Review (Top Submissions Only)
- Reviewed by **Meta and HuggingFace engineers**
- Checked for: real-world utility, creativity, exploit resistance
- They will try to break your grader — make it robust

---

## EVALUATION CRITERIA (Scoring Weights)

| Parameter | Weight | What Judges Look For |
|-----------|--------|----------------------|
| **Real-world utility** | 30% | Does it model a genuine task? Would someone actually use this to train/evaluate agents? |
| **Task & grader quality** | 25% | Are tasks well-defined? Do graders accurately and fairly measure success? Meaningful difficulty progression? |
| **Environment design** | 20% | Clean state management, sensible action/observation spaces, good reward shaping, proper episode boundaries |
| **Code quality & spec compliance** | 15% | Follows OpenEnv spec, clean project structure, typed models, documented, tested, Dockerfile works |
| **Creativity & novelty** | 10% | Novel problem domain, interesting mechanics, clever reward design, original approach |

---

## DISQUALIFICATION CRITERIA ❌

These will get you **immediately eliminated**, no appeal:

| Violation | Why it kills you |
|-----------|-----------------|
| Environment does not deploy or respond | Phase 1 auto-fail |
| Plagiarized or trivially modified existing environments | Human review catches this |
| Graders that always return the same score | Phase 2 variance check catches this |
| No baseline inference script | Phase 1 auto-fail |

### Additional things that will hurt you badly:
- Grader that can be exploited (agent submits garbage and gets 1.0)
- Reward function that only scores at episode end (no partial progress)
- `openenv.yaml` missing or malformed
- Dockerfile that builds but crashes at runtime
- README missing action/observation space definitions
- Tasks with subjective or non-deterministic graders

---

## QUICK CHECKLIST BEFORE SUBMISSION

```
[ ] openenv.yaml exists and is valid
[ ] step() returns (observation, reward, done, info)
[ ] reset() returns initial observation
[ ] state() returns current state
[ ] All 3 models are typed Pydantic models
[ ] 3 tasks exist with easy/medium/hard difficulty
[ ] Each task has a programmatic grader (0.0 - 1.0)
[ ] Reward gives partial credit, not just binary end score
[ ] Baseline script runs with OPENAI_API_KEY env var
[ ] Baseline script produces same scores on re-run
[ ] Dockerfile builds cleanly
[ ] docker run starts environment without errors
[ ] HF Space is live and tagged with 'openenv'
[ ] README has: description, action space, observation space, tasks, setup, baseline scores
[ ] Grader cannot be trivially exploited
[ ] No hardcoded/static scores in graders
```

---

## OUR ENVIRONMENT SUMMARY

**Name:** SQL Query Optimizer Environment
**Domain:** Database / SQL
**Database:** SQLite (zero infra, runs anywhere in Docker)

**Action Space:** Agent submits a SQL query string
**Observation Space:** Schema definition + broken/slow query + error message (if any) + current score

**Reward Function:**
- Correctness score: does the result match expected output?
- Efficiency score: is the query plan better than the original?
- Partial credit: awarded for syntactically valid queries even if wrong
- Penalty: for queries that drop/modify tables or cause errors

**Tasks:**
1. Easy — Fix broken SELECT (wrong column, missing WHERE clause)
2. Medium — Rewrite inefficient JOIN or GROUP BY
3. Hard — Optimize nested subquery using CTE or window function
