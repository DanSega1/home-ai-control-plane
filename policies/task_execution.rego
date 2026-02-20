package homeai.task

import future.keywords.if
import future.keywords.in

# ---------------------------------------------------------------------------
# Default deny
# ---------------------------------------------------------------------------

default allow = false
default deny_reasons = []

# ---------------------------------------------------------------------------
# Allow rule
# ---------------------------------------------------------------------------

allow if {
    not task_blocked
    not budget_exceeded
    not requires_unapproved_destructive
    valid_status_transition
}

# ---------------------------------------------------------------------------
# Status transition guard
# ---------------------------------------------------------------------------

# Only allow transitions that are valid in the task lifecycle
valid_transitions := {
    "pending":            {"planning"},
    "planning":           {"awaiting_approval", "failed"},
    "awaiting_approval":  {"approved", "rejected"},
    "approved":           {"executing", "policy_denied"},
    "executing":          {"completed", "failed"},
}

valid_status_transition if {
    valid_transitions[input.current_status][input.requested_status]
}

# ---------------------------------------------------------------------------
# Blocked states
# ---------------------------------------------------------------------------

task_blocked if {
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

deny_reasons := reasons if {
    reasons := [r |
        task_blocked
        r := sprintf("task is in terminal state: %v", [input.current_status])
    ] | [r |
        budget_exceeded
        r := "monthly budget limit exceeded"
    ] | [r |
        requires_unapproved_destructive
        r := sprintf("risk level %v requires human approval", [input.plan.risk_level])
    ] | [r |
        not valid_status_transition
        r := sprintf("invalid status transition: %v -> %v", [input.current_status, input.requested_status])
    ]
}
