package homeai.budget

import future.keywords.if

# ---------------------------------------------------------------------------
# Default deny
# ---------------------------------------------------------------------------

default allow := false

# ---------------------------------------------------------------------------
# Allow rule – budget headroom and per-task cap check
# ---------------------------------------------------------------------------

allow if {
	not monthly_budget_exceeded
	not per_task_cap_exceeded
}

# ---------------------------------------------------------------------------
# Monthly budget cap
# ---------------------------------------------------------------------------

monthly_budget_exceeded if {
	input.monthly_tokens_used + input.estimated_tokens > input.monthly_token_limit
}

monthly_budget_exceeded if {
	input.monthly_cost_usd + input.estimated_cost_usd > input.monthly_cost_limit_usd
}

# ---------------------------------------------------------------------------
# Per-task token cap
# ---------------------------------------------------------------------------

per_task_cap_exceeded if {
	input.estimated_tokens > input.per_task_token_limit
}

# ---------------------------------------------------------------------------
# Remaining budget helpers (exposed as OPA data for callers)
# ---------------------------------------------------------------------------

remaining_tokens := input.monthly_token_limit - input.monthly_tokens_used

remaining_cost_usd := input.monthly_cost_limit_usd - input.monthly_cost_usd

deny_reason := msg if {
	monthly_budget_exceeded
	msg := sprintf(
		"monthly budget exceeded: used %v / %v tokens",
		[input.monthly_tokens_used, input.monthly_token_limit],
	)
}

deny_reason := msg if {
	not monthly_budget_exceeded
	per_task_cap_exceeded
	msg := sprintf(
		"per-task token cap exceeded: estimated %v > limit %v",
		[input.estimated_tokens, input.per_task_token_limit],
	)
}
