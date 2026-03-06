# API Reference

All services expose a `GET /health` endpoint. The Supervisor is the primary external-facing API.

---

## Supervisor — `http://localhost:8000`

### `POST /tasks`

Create a new task. Planning starts automatically after creation.

**Request body:**
```json
{
  "title": "string",
  "description": "string",
  "requestor": "user",
  "approval_tier": "high"
}
```

`approval_tier` values: `low` | `medium` | `high` | `critical` (default: `high`)

**Response:** `Task` object (201)

---

### `GET /tasks`

List tasks, optionally filtered by status.

**Query parameters:**
| Param | Type | Description |
|---|---|---|
| `status` | string (optional) | Filter by task status |
| `limit` | int (1–200, default 50) | Max results |

**Response:** Array of `Task` objects

---

### `GET /tasks/{task_id}`

Get a single task by ID.

**Response:** `Task` object (404 if not found)

---

### `POST /tasks/{task_id}/approve`

Approve a task that is `awaiting_approval`. Triggers OPA validation and execution immediately.

**Response:** Updated `Task` object

---

### `POST /tasks/{task_id}/reject`

Reject a task that is `awaiting_approval`.

**Response:** Updated `Task` object

---

### `POST /tasks/{task_id}/execute`

Manually trigger execution of an `approved` task (normally called automatically after approval).

**Response:** Updated `Task` object (400 if task is not in `approved` state)

---

### `PATCH /tasks/{task_id}`

Partial update. Used internally by Notion Sync to write back the Notion page ID.

**Request body:**
```json
{
  "notion_page_id": "string"
}
```

**Response:** Updated `Task` object

---

## Planner Agent — `http://localhost:8001`

### `POST /plan`

Generate an `ExecutionPlan` from a task description. Called by the Supervisor; not typically called directly.

**Request body:**
```json
{
  "task_id": "string",
  "title": "string",
  "description": "string"
}
```

**Response:**
```json
{
  "plan": { ... },
  "tokens_used": 450,
  "model": "gpt-4o-mini"
}
```

---

## Skill Runner — `http://localhost:8002`

### `POST /execute`

Execute an `ExecutionPlan`. Called by the Supervisor; not typically called directly.

**Request body:**
```json
{
  "task_id": "string",
  "plan": { ... }
}
```

**Response:** `TaskResult` object

```json
{
  "success": true,
  "output": { "step-uuid": { "output": "...", "tool_calls": [...] } },
  "error": null,
  "tokens_used": 1200,
  "duration_seconds": 4.5
}
```

---

## Common Models

### `Task`

```json
{
  "task_id": "uuid",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "title": "string",
  "description": "string",
  "requestor": "user",
  "status": "pending | planning | awaiting_approval | approved | rejected | policy_denied | executing | completed | failed | cancelled",
  "approval_tier": "low | medium | high | critical",
  "plan": null,
  "result": null,
  "audit_trail": [],
  "notion_page_id": null,
  "total_tokens_used": 0,
  "iteration_count": 0,
  "max_iterations": 10
}
```

### `ExecutionPlan`

```json
{
  "plan_id": "uuid",
  "steps": [ { "ExecutionStep" } ],
  "estimated_total_tokens": 1500,
  "approval_tier": "high",
  "risk_level": "low",
  "requires_snapshot": false,
  "reasoning": "string"
}
```

### `ExecutionStep`

```json
{
  "step_id": "uuid",
  "skill": "raindrop-io",
  "action": "Save URL to research collection",
  "instruction": "Save https://example.com to the Research collection",
  "context": {},
  "depends_on": [],
  "estimated_tokens": 500,
  "reversible": true
}
```

### `TaskResult`

```json
{
  "success": true,
  "output": {},
  "error": null,
  "tokens_used": 1200,
  "duration_seconds": 4.5
}
```
