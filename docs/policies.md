# Policies

OPA enforces three policy packages at `policies/homeai/`. Policies are mounted read-only and hot-reloaded — edit a `.rego` file and OPA picks up the change without restarting.

The Supervisor calls OPA synchronously in three phases before any execution:

1. **Task execution check** → `homeai/task`
2. **Budget check** → `homeai/budget`
3. **Skill access check** → `homeai/skill` (once per plan step)

---

## `homeai/task` — Task Execution Policy

**File:** `policies/homeai/task/task.rego`

Controls whether a status transition is allowed.

### Allow conditions (all must be true)

| Condition | Description |
|---|---|
| `valid_status_transition` | The `current_status → requested_status` pair is in the allowed transition table |
| `not blocked` | Task is not already in a terminal state |
| `not budget_exceeded` | `input.budget.budget_exceeded` is not `true` |
| `not requires_unapproved_destructive` | High/critical risk plans require `current_status == "approved"` |

### Valid status transitions

| From | To |
|---|---|
| `pending` | `planning` |
| `planning` | `awaiting_approval`, `failed` |
| `awaiting_approval` | `approved`, `rejected` |
| `approved` | `executing`, `policy_denied` |
| `executing` | `completed`, `failed` |

### OPA input shape

```json
{
  "current_status": "approved",
  "requested_status": "executing",
  "plan": {
    "risk_level": "low",
    "requires_snapshot": false,
    "approval_tier": "high"
  },
  "budget": {
    "budget_exceeded": false
  }
}
```

### Deny reasons

The `deny_reasons` array is returned on denial and logged to the audit trail.

---

## `homeai/budget` — Budget Policy

**File:** `policies/homeai/budget/budget.rego`

Enforces monthly token/cost caps and per-task token limits.

### Allow conditions (all must be true)

| Condition | Description |
|---|---|
| `not monthly_budget_exceeded` | `monthly_tokens_used + estimated_tokens ≤ monthly_token_limit` AND `monthly_cost_usd + estimated_cost_usd ≤ monthly_cost_limit_usd` |
| `not per_task_cap_exceeded` | `estimated_tokens ≤ per_task_token_limit` |

### OPA input shape

```json
{
  "monthly_tokens_used": 12000,
  "monthly_token_limit": 500000,
  "monthly_cost_usd": 0.24,
  "monthly_cost_limit_usd": 10.0,
  "estimated_tokens": 1500,
  "estimated_cost_usd": 0.03,
  "per_task_token_limit": 20000
}
```

### Default limits (configurable via Supervisor env)

| Limit | Default |
|---|---|
| Monthly token limit | 500,000 |
| Monthly cost limit | $10.00 |
| Per-task token limit | 20,000 |

---

## `homeai/skill` — Skill Access Policy

**File:** `policies/homeai/skill/skill.rego`

Controls which agents can invoke which skills, and whether destructive skills require approval.

### Allow conditions (all must be true)

| Condition | Description |
|---|---|
| `is_skill_known` | Skill ID exists in the OPA registry |
| `agent_permitted` | The calling agent is listed in `agent_skill_permissions` for that skill |
| `not high_risk_without_approval` | Destructive skills with `high`/`critical` risk require `task_status == "approved"` |

### Skill registry (in policy)

```rego
registry := {
  "raindrop-io": {"risk": "low", "destructive": true}
}
```

> **Note:** When adding a new skill to `skills/registry.yaml`, also add it here.

### Agent permissions (in policy)

```rego
agent_skill_permissions := {
  "planner":    {"raindrop-io"},
  "supervisor": {"raindrop-io"},
}
```

### OPA input shape

```json
{
  "skill": "raindrop-io",
  "agent": "supervisor",
  "task_status": "approved",
  "plan_risk_level": "low"
}
```

---

## Updating Policies

Policies are version-controlled in `policies/`. OPA watches the directory for changes.

When adding a new skill, update **both**:
1. `skills/registry.yaml` — for the Skill Runner runtime
2. `policies/homeai/skill/skill.rego` — for the OPA policy registry

To test policies locally without running the full stack:

```bash
# Evaluate a task execution decision
echo '{"input": {"current_status": "approved", "requested_status": "executing", "plan": {"risk_level": "low", "requires_snapshot": false}, "budget": {"budget_exceeded": false}}}' \
  | curl -s -X POST http://localhost:8181/v1/data/homeai/task/allow \
    -H 'Content-Type: application/json' -d @-
```
