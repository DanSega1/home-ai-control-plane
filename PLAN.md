# Conductor Engine + Home Control Plane Development Plan

## Summary

This roadmap replaces the existing single-track `PLAN.md` and becomes the canonical plan for both layers:

- **Conductor Engine** is the generic framework: task runtime, agents, capabilities, policy hooks, storage abstractions, and execution workflows.
- **Home AI Control Plane** is the first production application built on top of that framework.

Current status: **Phase 1 is partially complete**. The engine runtime, capability registry, local task store/queue, built-in capabilities, docs-first contracts, and `cond` CLI have now been extracted into the separate `Conductor-Engine` repository. Phase 1 now focuses on package publication and hardening Home AI Control Plane’s dependency on the extracted framework.

## Implementation Plan

### Phase 1 — Foundation (Engine v0.1, partially complete)

**Status:** In progress

**Done overall:**
- docs-first engine contracts exist
- minimal runtime exists
- capability registry/loader exists
- `cond` CLI exists
- local JSON task store + in-memory queue exist
- built-in capabilities exist
- optional memU-backed memory abstraction/plugin exists
- the framework has been split into the `Conductor-Engine` repository

**Still pending:**
- publish the framework as a versioned package
- switch Home AI Control Plane to consume the published package
- complete install/distribution hardening for a clean standalone release

- Freeze the Phase 1 public surface around `TaskSubmission`, `TaskRecord`, `TaskStatus`, `Capability`, `CapabilityRegistry`, `TaskStore`, and `cond`.
- Keep the runtime planner-free: `Task -> Supervisor -> Capability -> Result`.
- Complete packaging so `conductor-engine` is installable and runnable independently of the Home app.
- Repository split is complete: `Conductor-Engine` now holds the generic `engine/`, CLI, engine docs, and engine tests, while `home-ai-control-plane` keeps the Home-specific services/contracts/policies.
- Publish `conductor-engine` as a versioned Python package and make Home AI Control Plane consume it as a pinned dependency.
- Exit criteria:
  - `pip install conductor-engine` works in a clean environment
  - `cond run`, `cond capability list`, and `cond task list` work without Home-specific code
  - built-in capabilities load dynamically
  - Home AI Control Plane runs against the published package instead of in-repo engine code

### Phase 2 — Agent Layer

**Status:** Not started

- Introduce logical agent roles in the framework: `PlannerAgent`, `WorkerAgent`, and `ValidatorAgent`.
- Upgrade the task model from single-capability execution to planned execution with `goal`, `plan`, `steps`, `result`, and `evaluation`.
- Define the execution loop as `Task -> Planner -> Worker -> Validator -> Supervisor decision`.
- Add retries, iteration limits, partial-success handling, and failure recovery in the supervisor.
- Keep agents optional: the engine must still support deterministic non-agent execution paths.

### Phase 3 — Governance & Safety

**Status:** Not started in the framework

Note: Home AI Control Plane already has app-level OPA/policy and approval mechanisms, but the generic engine-level governance layer is not yet implemented.

- Add a framework-level `PolicyEngine.authorize(action, context)` contract with adapters for local rules and OPA.
- Move risk classification into capability metadata with `low`, `medium`, `high`, and `critical`.
- Add approval hooks for high-risk tasks before execution.
- Expand guardrails to cover schema validation, tool filtering, input checks, and output validation.
- Keep policy enforcement generic in the engine; Home-specific approval UX stays in the app layer.

### Phase 4 — Storage & Scaling

**Status:** Not started

- Formalize framework storage contracts: `TaskStore`, `Queue`, and optional execution-state/locking primitives.
- Implement adapters for memory/local storage first, then Postgres, Mongo, and Redis or Valkey.
- Add task claiming and locking so multiple supervisors can operate safely.
- Shift the worker model from in-process execution to `Supervisor -> Queue -> Workers -> Result`.

### Phase 5 — Runtime Modes

**Status:** Not started

- Support four runtime targets from the same engine package: local single-process, Docker, Kubernetes/Helm, and agent-hosted platforms.
- Keep runtime mode as deployment/configuration, not a forked code path.

### Phase 6 — Observability

**Status:** Not started

- Add framework-native metrics for execution time, success rate, retries, token usage, and failures.
- Emit structured logs and expose Prometheus-compatible metrics.
- Keep Grafana and dashboarding in deployment/app integrations rather than core engine code.

### Phase 7 — Plugin Ecosystem

**Status:** Not started

- Standardize plugin packaging around Python packages first, with Git-based install as a secondary path for early plugins.
- Define a capability manifest format for name, inputs, risk level, and capability metadata.
- Keep capability loading registry-driven and package-based; Home app skills and app integrations should become engine plugins over time where practical.

### Phase 8 — Home AI Control Plane

**Status:** In progress

- Rebuild Home AI Control Plane explicitly as an app on top of `conductor-engine`.
- Keep Home-specific integrations here: Raindrop, Notion, Google, GitHub, Home Assistant, Plex/ARR, PKM workflows, approval UX, and homelab automation.
- Replace direct internal engine assumptions with package-level engine APIs.
- Use the app as the primary proving ground for framework features before promoting them into engine core.

### Phase 9 — Advanced Features

**Status:** Not started

- Add optional scoring, agent performance tracking, agent creation/guild workflows, learning loops, and recommendation features only after the framework and app boundaries are stable.
- Treat this phase as experimental and explicitly non-blocking for v0.x adoption.

## Public Interfaces and Defaults

- **Phase 1 engine contracts**
  - Task: `TaskSubmission`, `TaskRecord`, `TaskStatus`, `TaskResult`
  - Execution: `TaskSupervisor`
  - Capability system: `Capability`, `CapabilityDescriptor`, `CapabilityContext`, `CapabilityResult`, `CapabilityRegistry`
  - Storage: `TaskStore`, local JSON store, in-memory queue
  - CLI: `cond run`, `cond capability list`, `cond task list`
- **Phase 2 additions**
  - Agent contracts: planner, worker, validator roles
  - Planned task structure with explicit `goal`, `plan`, `steps`, `result`, `evaluation`
- **Phase 3 additions**
  - `PolicyEngine` authorization interface
  - approval and risk metadata at the framework level
- Defaults chosen:
  - canonical planning doc is top-level `PLAN.md`
  - repo split happens in Phase 1, before Phase 2
  - Home AI Control Plane consumes `conductor-engine` as a **published package**
  - AI remains optional; deterministic execution stays supported
  - framework core stays generic and free of Home-specific policy, skill, or infra assumptions

## Test Plan and Acceptance

- **Phase 1**
  - engine contract tests for task/capability/storage models
  - CLI smoke tests for `cond run`, `cond capability list`, `cond task list`
  - capability loading tests for built-ins and plugin registration
  - filesystem guardrail tests for path confinement
  - package install smoke test in a clean environment
  - Home app integration test proving it imports and runs against the published engine package
- **Phase 2**
  - planner/worker/validator loop tests, retry behavior, iteration caps, and partial-success cases
- **Phase 3**
  - policy allow/deny tests, approval-required flow tests, and risk-level enforcement
- **Phase 4**
  - multi-supervisor claim/lock tests and queue adapter tests
- **Phase 5–8**
  - deployment smoke tests per runtime mode, observability endpoint checks, plugin manifest validation, and end-to-end Home Control Plane workflows

## Assumptions

- The extracted engine slice in `Conductor-Engine` is the seed of the long-term framework, not throwaway prototype code.
- The framework has already been extracted into `Conductor-Engine`; the remaining dependency goal is to move from git-based consumption to a published package release.
- The framework is allowed to evolve during `v0.x`, but only documented public contracts should be treated as stable by the Home app.
- Foundation-first remains the governing rule: if a feature belongs to the framework long-term, it should be generalized there before adding Home-only variants.
