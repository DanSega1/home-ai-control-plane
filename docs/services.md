# Services

## Supervisor (`services/supervisor` · port 8000)

The orchestration engine and the only entry point for external requests. It owns the task lifecycle state machine and coordinates all other services.

**Responsibilities:**
- Accept task creation requests and persist them to MongoDB
- Call the Planner agent to generate an `ExecutionPlan`
- Gate execution behind OPA policy checks
- Trigger Skill Runner execution
- Maintain the full audit trail on every task

**Key modules:**
| Module | Purpose |
|---|---|
| `app/routes/tasks.py` | HTTP endpoints (`/tasks`, `/tasks/{id}/approve`, etc.) |
| `app/services/task_service.py` | Task lifecycle logic (`create_task`, `plan_task`, `execute_task`) |
| `app/opa_client.py` | OPA HTTP calls for task, budget, and skill checks |
| `app/db.py` | MongoDB async client |
| `app/config.py` | Settings via `pydantic-settings` |

**Configuration (`.env.supervisor`):**

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | `mongodb://mongo:27017` | MongoDB connection string |
| `MONGO_DB` | `homeai` | Database name |
| `OPA_URL` | `http://opa:8181` | OPA server URL |
| `PLANNER_URL` | `http://planner:8001` | Planner agent URL |
| `SKILL_RUNNER_URL` | `http://skill-runner:8002` | Skill Runner URL |
| `NOTION_SYNC_URL` | `http://notion-sync:8003` | Notion Sync URL |
| `MONTHLY_TOKEN_LIMIT` | `500000` | Monthly token budget cap |
| `MONTHLY_COST_LIMIT_USD` | `10.0` | Monthly cost budget cap (USD) |
| `PER_TASK_TOKEN_LIMIT` | `20000` | Per-task token cap |

---

## Planner Agent (`agents/planner` · port 8001)

A single-purpose FastAPI service that converts a natural-language task description into a structured `ExecutionPlan` using LiteLLM.

**Responsibilities:**
- Receive a task title + description from the Supervisor
- Call LiteLLM with a structured output prompt
- Return a valid `ExecutionPlan` with `ExecutionStep` entries, risk level, approval tier, and token estimate

**Key modules:**
| Module | Purpose |
|---|---|
| `app/routes/plan.py` | `POST /plan` endpoint |
| `app/planner.py` | LiteLLM call + response parsing |
| `app/config.py` | Settings |

**Configuration (`.env.planner`):**

| Variable | Description |
|---|---|
| `LITELLM_URL` | URL of the LiteLLM proxy (e.g. `http://litellm:4000`) |
| `PLANNER_MODEL` | Model to use (e.g. `gpt-4o-mini`) |

---

## Skill Runner (`services/skill-runner` · port 8002)

The isolated execution boundary. It receives an `ExecutionPlan` from the Supervisor and drives a tool-call loop per step using the skill's `SKILL.md` as the LLM system prompt.

**Responsibilities:**
- Load skill metadata and `SKILL.md` from the registry at startup
- For each plan step: build the prompt, call LiteLLM, dispatch MCP tool calls, loop until done
- Respect `depends_on` ordering between steps
- Return a `TaskResult` with outputs and token usage

**Key modules:**
| Module | Purpose |
|---|---|
| `app/routes/execute.py` | `POST /execute` endpoint |
| `app/skill_executor.py` | LLM + MCP tool-call loop per step |
| `app/skill_loader.py` | Fetches and caches `SKILL.md` from GitHub / skillstore |
| `app/registry.py` | Parses `skills/registry.yaml` |
| `app/mcp_client.py` | MCP SSE / stdio client |

**Configuration (`.env.skill-runner`):**

| Variable | Description |
|---|---|
| `LITELLM_URL` | LiteLLM proxy URL |
| `SKILL_RUNNER_MODEL` | Model to use for skill execution |
| `RAINDROP_MCP_TOKEN` | Bearer token for Raindrop.io MCP server |
| `GITHUB_TOKEN` | (Optional) Token for fetching `SKILL.md` from private repos |

**Skills volume:** `skills/` is mounted read-only at `/app/skills`. Changes to `registry.yaml` take effect on the next container restart.

---

## Notion Sync (`services/notion-sync` · port 8003)

Mirrors task state to a Notion Kanban board and polls for human approval decisions.

**Responsibilities:**
- When a task reaches `awaiting_approval`, create (or update) a Notion card
- Poll Notion periodically for status changes (approved / rejected)
- Call `PATCH /tasks/{id}` on the Supervisor to write back the Notion page ID
- Call `POST /tasks/{id}/approve` or `/reject` based on the Notion card status

**Key modules:**
| Module | Purpose |
|---|---|
| `app/notion_client.py` | Notion API wrapper |
| `app/sync.py` | Polling loop + sync logic |
| `app/config.py` | Settings |

**Configuration (`.env.notion-sync`):**

| Variable | Description |
|---|---|
| `NOTION_TOKEN` | Notion integration token |
| `NOTION_DATABASE_ID` | ID of the Kanban database in Notion |
| `SUPERVISOR_URL` | Supervisor URL (e.g. `http://supervisor:8000`) |
| `POLL_INTERVAL_SECONDS` | How often to poll Notion (default: 30) |

---

## LiteLLM (third-party · port 4000)

Model router and proxy. All LLM calls from Planner and Skill Runner go through LiteLLM, allowing providers to be swapped without touching service code.

**Configuration:** `config/litellm_config.yaml` — define models, providers, fallbacks, and cost tracking. The env file `config/.env.litellm` holds provider API keys (e.g. `OPENAI_API_KEY`).

---

## OPA (third-party · port 8181)

Open Policy Agent policy engine. Mounts `policies/` read-only and hot-reloads changes.

OPA is called synchronously by the Supervisor before each execution phase. See [policies.md](policies.md) for policy details.

---

## MongoDB (third-party · port 27017)

Persistent store for two collections:

| Collection | Contents |
|---|---|
| `tasks` | All `Task` documents (full history, never deleted) |
| `model_usage` | `ModelUsageRecord` entries per LLM call |
