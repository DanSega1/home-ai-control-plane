package homeai.task

import future.keywords.if
import future.keywords.in

# ---------------------------------------------------------------------------
# Allow rule
# ---------------------------------------------------------------------------

allow if {
	not blocked
	not budget_exceeded
	not requires_unapproved_destructive
	valid_status_transition
}

# ---------------------------------------------------------------------------
# Status transition guard
# ---------------------------------------------------------------------------

# Only allow transitions that are valid in the task lifecycle
valid_transitions := {
	"pending": {"planning"},
	"planning": {"awaiting_approval", "failed"},
	"awaiting_approval": {"approved", "rejected"},
	"approved": {"executing", "policy_denied"},
	"executing": {"completed", "failed"},
}

valid_status_transition if {
	valid_transitions[input.current_status][input.requested_status]
}

# ---------------------------------------------------------------------------
# Blocked states
# ---------------------------------------------------------------------------

blocked if {
	input.current_status in {"completed", "failed", "cancelled", "rejected", "policy_denied"}
}

# ---------------------------------------------------------------------------
# Budget guard
# ---------------------------------------------------------------------------

budget_exceeded if {
	input.budget.budget_exceeded == true
}

# ---------------------------------------------------------------------------
# Destructive actions require approval
# ---------------------------------------------------------------------------

requires_unapproved_destructive if {
	input.plan.risk_level in {"high", "critical"}
	input.current_status != "approved"
}

requires_unapproved_destructive if {
	input.plan.requires_snapshot == true
	input.current_status != "approved"
}

# ---------------------------------------------------------------------------
# Deny reasons (useful for debugging / audit)
# ---------------------------------------------------------------------------

default _reason_terminal := []

_reason_terminal := [sprintf("task is in terminal state: %v", [input.current_status])] if blocked

default _reason_budget := []

_reason_budget := ["monthly budget limit exceeded"] if budget_exceeded

default _reason_destructive := []

_reason_destructive := [sprintf("risk level %v requires human approval", [input.plan.risk_level])] if {
	requires_unapproved_destructive
}

default _reason_transition := []

_reason_transition := [sprintf(
	"invalid status transition: %v -> %v",
	[input.current_status, input.requested_status],
)] if {
	not valid_status_transition
}

deny_reasons := array.flatten([
	_reason_terminal,
	_reason_budget,
	_reason_destructive,
	_reason_transition,
])
