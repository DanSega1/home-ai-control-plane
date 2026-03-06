# Data Model

All shared Pydantic models live in `contracts/`. Every service imports from this package — no service defines its own task or usage models.

---

## `contracts/task.py`

### `TaskStatus` (StrEnum)

| Value | Description |
|---|---|
| `pending` | Just created |
| `planning` | Planner is generating a plan |
| `awaiting_approval` | Waiting for human sign-off |
| `approved` | Approved by human (or auto-approved) |
| `rejected` | Rejected by human |
| `policy_denied` | OPA blocked execution |
| `executing` | Skill Runner is working |
| `completed` | Finished successfully |
| `failed` | Finished with an error |
| `cancelled` | Cancelled by user or supervisor |

### `ApprovalTier` (StrEnum)

| Value | Behavior |
|---|---|
| `low` | Auto-approved if risk is also low |
| `medium` | Notify only |
| `high` | Manual approval required |
| `critical` | Multi-step approval |

### `RiskLevel` (StrEnum)

`low` | `medium` | `high` | `critical`

### `ExecutionStep`

| Field | Type | Description |
|---|---|---|
| `step_id` | str (UUID) | Auto-generated |
| `skill` | str | Skill ID from `registry.yaml` (e.g. `raindrop-io`) |
| `action` | str | Human-readable summary of what this step does |
| `instruction` | str | Natural language instruction passed to the skill executor |
| `context` | dict | Optional structured context for the instruction |
| `depends_on` | list[str] | `step_id`s this step must wait for |
| `estimated_tokens` | int | Planner's token estimate for this step |
| `reversible` | bool | Whether this step can be undone |

### `ExecutionPlan`

| Field | Type | Description |
|---|---|---|
| `plan_id` | str (UUID) | Auto-generated |
| `steps` | list[ExecutionStep] | Ordered steps (DAG via `depends_on`) |
| `estimated_total_tokens` | int | Sum of all step estimates |
| `approval_tier` | ApprovalTier | Tier assigned by the Planner |
| `risk_level` | RiskLevel | Overall risk assessed by the Planner |
| `requires_snapshot` | bool | Whether a backup must be taken before execution |
| `reasoning` | str | Planner's explanation of the plan |

### `AuditEntry`

| Field | Type | Description |
|---|---|---|
| `timestamp` | datetime | UTC timestamp |
| `actor` | str | `supervisor`, `planner`, `opa`, `notion-sync`, `user` |
| `action` | str | E.g. `task_created`, `execution_started`, `policy_denied` |
| `detail` | str \| None | Optional extra context |

### `TaskResult`

| Field | Type | Description |
|---|---|---|
| `success` | bool | Whether execution succeeded |
| `output` | Any | Step outputs keyed by `step_id` |
| `error` | str \| None | Error message if `success=False` |
| `tokens_used` | int | Total tokens consumed during execution |
| `duration_seconds` | float | Wall-clock execution time |

### `Task` (primary document)

| Field | Type | Description |
|---|---|---|
| `task_id` | str (UUID) | Primary key |
| `created_at` | datetime | Creation time |
| `updated_at` | datetime | Last modification time |
| `title` | str | Short task title |
| `description` | str | Full task description |
| `requestor` | str | Who initiated (default: `"user"`) |
| `status` | TaskStatus | Current lifecycle state |
| `approval_tier` | ApprovalTier | Approval requirement |
| `plan` | ExecutionPlan \| None | Set after planning |
| `result` | TaskResult \| None | Set after execution |
| `audit_trail` | list[AuditEntry] | Full history of state changes |
| `notion_page_id` | str \| None | Notion card ID (set by Notion Sync) |
| `total_tokens_used` | int | Cumulative token count (planning + execution) |
| `iteration_count` | int | Number of execution attempts |
| `max_iterations` | int | Guard limit (default: 10) |

### API Models

**`CreateTaskRequest`** — POST body for `POST /tasks`:
- `title`, `description`, `requestor` (default `"user"`), `approval_tier` (default `high`)

**`TaskStatusResponse`** — lightweight status check response:
- `task_id`, `status`, `approval_tier`, `notion_page_id`, `result`

---

## `contracts/model_usage.py`

### `ModelUsageRecord`

Stored in MongoDB `model_usage` collection. One record per LLM call.

| Field | Type | Description |
|---|---|---|
| `record_id` | str (UUID) | Auto-generated |
| `task_id` | str \| None | Associated task (if any) |
| `agent` | str | `"planner"` or `"supervisor"` |
| `model` | str | Model name (e.g. `"gpt-4o-mini"`) |
| `prompt_tokens` | int | Input token count |
| `completion_tokens` | int | Output token count |
| `total_tokens` | int | Sum of prompt + completion |
| `cost_usd` | float | Estimated cost |
| `timestamp` | datetime | UTC call time |

### `BudgetStatus`

Computed by the Supervisor from the `model_usage` collection and passed to OPA.

| Field | Type | Description |
|---|---|---|
| `month` | str | `"YYYY-MM"` |
| `tokens_used` | int | Tokens used this month |
| `tokens_limit` | int | Monthly token limit |
| `cost_usd` | float | Cost this month (USD) |
| `cost_limit_usd` | float | Monthly cost limit (USD) |
| `remaining_tokens` | int | `tokens_limit - tokens_used` |
| `remaining_cost_usd` | float | `cost_limit_usd - cost_usd` |
| `budget_exceeded` | bool | `True` if either limit is reached |

---

## MongoDB Collections

| Collection | Primary key | Contents |
|---|---|---|
| `tasks` | `task_id` | All `Task` documents |
| `model_usage` | `record_id` | All `ModelUsageRecord` documents |

Tasks are never deleted — the collection is the complete audit history of all work the system has ever attempted.
