# 🧠 Home AI Control Plane – Implementation Plan

## Overview

This project implements a **policy-governed, multi-agent AI control plane** designed to manage:

* Personal digital workflows (Notion, PKM, automation)
* Home lab services (Docker, monitoring, backups)
* Smart home integrations
* Budget enforcement for LLM usage
* Skill-based extensibility
* Governance and approval workflows

The system is:

* Single-node (Raspberry Pi 5, 8GB RAM)
* Docker-based
* Policy-first (OPA enforced)
* Human-in-the-loop
* Secure-by-design
* Monorepo, multi-container architecture

---

# 🎯 Project Goals

1. Build a **Supervisor-based orchestration engine**
2. Enforce execution using **Open Policy Agent (OPA)**
3. Use **MongoDB as source of truth**
4. Provide human approvals via **Notion Kanban**
5. Isolate execution via a **Skill Runner**
6. Enforce **budget + iteration limits**
7. Support future expansion via **Agent Guild**
8. Maintain strong separation of:

   * Intelligence
   * Authority
   * Execution
   * Policy
   * State

---

# 🏗 Architecture Summary

```
User / Events
    ↓
LiteLLM Router
    ↓
Supervisor (Python)
    ↓
OPA (Policy Enforcement)
    ↓
Skill Runner (Execution Boundary)
    ↓
External Systems (Notion, Docker, APIs)

MongoDB = Source of Truth
```

---

# 🧱 Technology Stack

| Component     | Tech                                   |
| ------------- | -------------------------------------- |
| Supervisor    | Python (FastAPI)                       |
| Agents        | Python                                 |
| Policy Engine | OPA (Go)                               |
| Skill Runner  | Python (Phase 1) → Go (optional later) |
| Database      | MongoDB                                |
| Model Router  | LiteLLM                                |
| Deployment    | Docker Compose                         |
| Backup        | mongodump + encrypted archive          |
| Secrets       | Docker secrets / local secure files    |

---

# 🗂 Repository Structure

```
services/
  supervisor/
  notion-sync/
  skill-runner/

agents/
  planner/

policies/

contracts/

skills/
  raindrop-io/

infra/
  docker-compose.yml

config/
docs/
```

---

# 🚀 Implementation Phases

---

# Phase 1 – Minimal Viable Control Plane

## Objective

Build a fully functional but minimal system proving:

* Task lifecycle works
* OPA enforcement works
* Approval gating works
* One skill executes safely
* Budget enforcement works

## Components

* MongoDB
* OPA (basic policies)
* Supervisor
* Planner Agent
* LiteLLM integration
* Skill Runner (Raindrop skill)
* Notion Sync (task board only)

## Deliverable

End-to-end flow:

1. Create task
2. Planner generates structured plan
3. Await approval
4. Approve in Notion
5. OPA validates
6. Skill executes
7. Result logged in Mongo

---

# Phase 2 – Multi-Agent & Governance Expansion

## Objective

Introduce controlled specialization and orchestration.

## Add:

* Lab Agent (read-only)
* Backup Agent (snapshot-only)
* Risk scoring
* Iteration caps
* Pause / resume logic
* Agent Profiles registry
* Agent Guild (proposal-only mode)

## Deliverable

* Supervisor can route subtasks to role agents
* Agent Guild can propose new agents
* OPA validates agent creation
* Strict governance remains enforced

---

# Phase 3 – Lab & Automation Control

## Objective

Controlled interaction with home lab systems.

## Add:

* Docker inspection (read-only)
* Monitoring integration
* Snapshot system
* Backup automation
* Google Drive encrypted sync

## Deliverable

* System can monitor lab health
* Create backup tasks
* Propose container updates (approval required)

---

# Phase 4 – Hardening & Observability

## Objective

Production-level robustness.

## Add:

* Monitoring stack (Prometheus + Grafana)
* Health endpoints
* Audit dashboards
* Policy test suite
* Disaster recovery validation
* Documentation refinement

---

# 🛡 Governance Model

All execution follows:

```
Agent proposes
Supervisor routes
OPA authorizes
Skill executes
Mongo records
Human approves (if required)
```

### Approval Tiers

| Tier     | Behavior            |
| -------- | ------------------- |
| Low      | Auto-approve        |
| Medium   | Notify              |
| High     | Manual approval     |
| Critical | Multi-step approval |

Destructive actions always require approval.

---

# 💰 Budget Enforcement

* Track token usage in `model_usage` collection
* Enforce monthly budget cap
* OPA denies execution if limit exceeded
* Per-task token caps enforced

---

# 🔐 Security Model

* No direct shell access from LLM
* No Docker socket access
* No direct secret exposure to agents
* Secrets injected per service
* OPA mediates all execution
* Skill execution isolated
* Snapshot before destructive action

---

# 🔁 Backup Strategy

## Mongo

* Daily mongodump
* Encrypted archive
* Stored locally + remote encrypted storage

## Notion

* API-based export of AI-managed DBs
* Encrypted archive

---

# 📦 Development Strategy

* Develop locally
* Deploy to Pi via Docker Compose
* Weekly integration tests
* Keep policies versioned
* Keep configuration declarative
* Avoid overengineering

---

# 📈 Estimated Timeline (Side Project)

| Phase   | Duration   |
| ------- | ---------- |
| Phase 1 | 6–8 weeks  |
| Phase 2 | 4–6 weeks  |
| Phase 3 | 6–8 weeks  |
| Phase 4 | 6–10 weeks |

Total: 6–12 months sustainable pace.

---

# 🧠 Design Principles

* Policy-first
* Human-in-the-loop
* Deterministic state transitions
* Minimal implicit trust
* Strict separation of concerns
* Reversible actions
* Budget-aware reasoning
* Config-as-code
* State backed up independently

---

# 🧭 Future Possibilities

* k3s migration
* Multi-node scaling
* External dashboard
* SSO integration (Authentik)
* Advanced runtime guardrails
* Agent trust scoring

---

# 🏁 Definition of Success

The platform is successful when:

* It safely executes real automation tasks
* It cannot bypass governance
* It cannot exceed budget
* It can recover from failure
* It remains understandable and auditable
* It does not require constant babysitting