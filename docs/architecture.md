# Architecture

## Overview

Home AI Control Plane is a **policy-governed, multi-agent AI system** running on a single Raspberry Pi 5. It manages personal digital workflows and home-lab services through a layered architecture that enforces strict separation between intelligence, authority, execution, and state.

## Design Principles

- **Policy-first** — every execution transition passes through OPA before it happens
- **Human-in-the-loop** — tasks above `low` approval tier require explicit human sign-off
- **Deterministic state transitions** — the task lifecycle is a strict state machine
- **Minimal implicit trust** — agents cannot self-authorize; OPA decides
- **Reversible actions** — high-risk steps require a snapshot before execution
- **Budget-aware** — token and cost limits are enforced at the policy layer

## Component Map

```
User / Event
    │
    ▼
Supervisor  (:8000)          ← orchestration engine, state machine owner
    │
    ├──► Planner  (:8001)    ← natural language → structured ExecutionPlan
    │       └──► LiteLLM (:4000)
    │
    ├──► OPA  (:8181)        ← policy enforcement (task, budget, skill)
    │
    ├──► Notion Sync (:8003) ← human approval via Notion Kanban
    │       └──► Notion API
    │
    ├──► Skill Runner (:8002) ← isolated MCP execution boundary
    │       ├──► LiteLLM (:4000)
    │       └──► MCP Servers (Raindrop.io, …)
    │
    └──► MongoDB (:27017)    ← source of truth (tasks, model_usage)
```

## Docker Network

All services run inside a single bridge network named `homeai`. No service is reachable from outside the host except through the mapped ports below.

| Container | Port (host→container) | Role |
|---|---|---|
| `homeai-supervisor` | 8000→8000 | Orchestration API |
| `homeai-planner` | 8001→8001 | Planning agent |
| `homeai-skill-runner` | 8002→8002 | Skill execution |
| `homeai-notion-sync` | 8003→8003 | Notion board sync |
| `homeai-litellm` | 4000→4000 | Model router |
| `homeai-opa` | 8181→8181 | Policy engine |
| `homeai-mongo` | 27017→27017 | Database |

## Governance Flow

Every task passes through this sequence before any external action is taken:

```
1. Supervisor receives goal
2. Planner generates ExecutionPlan
3. OPA validates: task state transition + budget headroom + skill access
4. Human approves (if approval_tier > low)
5. OPA re-validates at execution time
6. Skill Runner executes plan steps via MCP
7. Result persisted to MongoDB with full audit trail
```

## Separation of Concerns

| Layer | Responsibility | Component |
|---|---|---|
| Intelligence | Goal → Plan translation | Planner + LiteLLM |
| Authority | Allow / deny decisions | OPA |
| Execution | Tool calls, MCP loop | Skill Runner |
| State | Task records, audit trail | MongoDB |
| Approval | Human sign-off | Notion Sync |
| Orchestration | Lifecycle coordination | Supervisor |

## Infrastructure

- **Runtime**: Docker Compose (single host, Raspberry Pi 5)
- **Data persistence**: named volume `mongo_data`
- **Policy hot-reload**: OPA mounts `policies/` read-only; changes are picked up without restart
- **Skills hot-swap**: Skill Runner mounts `skills/` read-only; `registry.yaml` is read at startup

## Dependency Management

All Python services share a single `constraints.txt` at the project root for pinned versions. Each service's `requirements.txt` lists only package names. Docker builds install with:

```dockerfile
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt
```

To upgrade a package, edit `constraints.txt` once — all services pick it up on next build.
