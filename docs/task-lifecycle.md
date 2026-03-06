# Task Lifecycle

## State Machine

```
PENDING
  │
  ▼ (plan_task)
PLANNING
  │
  ├──► FAILED          (planner error)
  │
  ▼ (plan generated)
AWAITING_APPROVAL      ← human reviews in Notion
  │
  ├──► REJECTED        (human rejects)
  │
  ▼ (human approves, or auto-approve for low-tier)
APPROVED
  │
  ├──► POLICY_DENIED   (OPA blocks execution)
  │
  ▼ (execute_task)
EXECUTING
  │
  ├──► FAILED          (skill runner error)
  │
  ▼
COMPLETED
```

Terminal states (no further transitions allowed): `completed`, `failed`, `cancelled`, `rejected`, `policy_denied`.

## Status Descriptions

| Status | Meaning |
|---|---|
| `pending` | Task created, planning not yet started |
| `planning` | Planner agent is generating an `ExecutionPlan` |
| `awaiting_approval` | Plan ready; waiting for human sign-off in Notion |
| `approved` | Human approved (or auto-approved for low-tier tasks) |
| `rejected` | Human rejected in Notion |
| `policy_denied` | OPA blocked execution (budget, risk, or state violation) |
| `executing` | Skill Runner is actively running plan steps |
| `completed` | All steps finished successfully |
| `failed` | An unrecoverable error occurred |
| `cancelled` | Cancelled by user or supervisor |

## Auto-Approval

Tasks with `approval_tier = low` AND `plan.risk_level = low` are automatically approved after planning. Execution starts immediately in the background without waiting for Notion.

## OPA Checks at Execution Time

Before a task transitions from `approved` → `executing`, the Supervisor runs three OPA checks in sequence:

1. **Task execution check** (`homeai.task`) — validates the status transition and budget snapshot
2. **Budget check** (`homeai.budget`) — validates estimated tokens + cost against monthly and per-task limits
3. **Skill access check** (`homeai.skill`) — run for each step in the plan

If any check fails, the task moves to `policy_denied`.

## Iteration Guard

Each task tracks `iteration_count` and `max_iterations` (default 10). The counter increments on each execution attempt. OPA can use this to prevent runaway re-execution (future phase).

## Audit Trail

Every state transition appends an `AuditEntry` to `task.audit_trail`:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "actor": "supervisor",
  "action": "execution_started",
  "detail": null
}
```

Actors recorded: `supervisor`, `planner`, `opa`, `notion-sync`, `user`.

## End-to-End Example

```bash
# 1. Create the task
curl -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title": "Save article", "description": "Save https://example.com to my research collection in Raindrop"}'
# → status: planning (then awaiting_approval automatically)

# 2. Check status
curl http://localhost:8000/tasks/{task_id}

# 3. Approve (or approve in the Notion board)
curl -X POST http://localhost:8000/tasks/{task_id}/approve
# → triggers OPA validation → skill execution → completed/failed

# 4. Reject instead
curl -X POST http://localhost:8000/tasks/{task_id}/reject
```
