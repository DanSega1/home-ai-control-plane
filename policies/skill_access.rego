package homeai.skill

import future.keywords.if
import future.keywords.in

# ---------------------------------------------------------------------------
# Default deny
# ---------------------------------------------------------------------------

default allow = false

# ---------------------------------------------------------------------------
# Skill registry – allowed skills and their risk levels
# ---------------------------------------------------------------------------

skill_registry := {
    "raindrop-io:bookmark_add":    {"risk": "low",    "destructive": false},
    "raindrop-io:bookmark_delete": {"risk": "high",   "destructive": true},
    "raindrop-io:collection_list": {"risk": "low",    "destructive": false},
    "raindrop-io:bookmark_search": {"risk": "low",    "destructive": false},
}

# ---------------------------------------------------------------------------
# Agent → allowed skills mapping
# ---------------------------------------------------------------------------

agent_skill_permissions := {
    "planner":    {"raindrop-io:bookmark_add", "raindrop-io:collection_list", "raindrop-io:bookmark_search"},
    "supervisor": {"raindrop-io:bookmark_add", "raindrop-io:bookmark_delete", "raindrop-io:collection_list", "raindrop-io:bookmark_search"},
}

# ---------------------------------------------------------------------------
# Allow rule
# ---------------------------------------------------------------------------

allow if {
    skill_known
    agent_permitted
    not destructive_without_approval
}

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

skill_known if {
    skill_registry[input.skill]
}

agent_permitted if {
    input.skill in agent_skill_permissions[input.agent]
}

destructive_without_approval if {
    skill_registry[input.skill].destructive == true
    input.task_status != "approved"
}

# ---------------------------------------------------------------------------
# Deny reason
# ---------------------------------------------------------------------------

deny_reason := msg if {
    not skill_known
    msg := sprintf("unknown skill: %v", [input.skill])
}

deny_reason := msg if {
    skill_known
    not agent_permitted
    msg := sprintf("agent %v is not permitted to call skill %v", [input.agent, input.skill])
}

deny_reason := msg if {
    skill_known
    agent_permitted
    destructive_without_approval
    msg := sprintf("skill %v is destructive and requires task status 'approved'", [input.skill])
}
