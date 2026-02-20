package homeai.skill

import future.keywords.if
import future.keywords.in

# ---------------------------------------------------------------------------
# Default deny
# ---------------------------------------------------------------------------

default allow = false

# ---------------------------------------------------------------------------
# Skill registry – registered skills and their risk profiles.
# Skill IDs match skills/registry.yaml.
# Destructive = true means the skill CAN perform deletes/writes with side-effects.
# ---------------------------------------------------------------------------

skill_registry := {
    "raindrop-io": {"risk": "low", "destructive": true},
}

# ---------------------------------------------------------------------------
# Agent → allowed skills mapping
# ---------------------------------------------------------------------------

agent_skill_permissions := {
    "planner":    {"raindrop-io"},
    "supervisor": {"raindrop-io"},
}

# ---------------------------------------------------------------------------
# Allow rule
# ---------------------------------------------------------------------------

allow if {
    skill_known
    agent_permitted
    not high_risk_without_approval
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

# Destructive skills require the task to be fully approved
high_risk_without_approval if {
    skill_registry[input.skill].destructive == true
    input.plan_risk_level in {"high", "critical"}
    input.task_status != "approved"
}

# ---------------------------------------------------------------------------
# Deny reason
# ---------------------------------------------------------------------------

deny_reason := msg if {
    not skill_known
    msg := sprintf("skill '%v' is not in the registry", [input.skill])
}

deny_reason := msg if {
    skill_known
    not agent_permitted
    msg := sprintf("agent '%v' is not permitted to use skill '%v'", [input.agent, input.skill])
}

deny_reason := msg if {
    skill_known
    agent_permitted
    high_risk_without_approval
    msg := sprintf("skill '%v' with risk level '%v' requires task status 'approved'", [input.skill, input.plan_risk_level])
}
