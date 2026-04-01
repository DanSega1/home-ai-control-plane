# Conductor Engine

This project consumes [`conductor-engine==0.6.0`](https://pypi.org/project/conductor-engine/0.6.0/) as its generic orchestration framework. The source repository lives at [DanSega1/Conductor-Engine](https://github.com/DanSega1/Conductor-Engine).

Conductor Engine is the framework layer under Home AI Control Plane. It provides the generic runtime primitives: task contracts, capability loading, execution supervision, retry handling, local storage, CLI tooling, and a workflow/orchestrator layer. Home AI Control Plane then adds app-specific services, OPA policy enforcement, human approval flows, and MCP-backed skills on top.

## What Conductor Engine Includes

Based on the current source in `../Conductor-Engine` and the published `0.6.0` package, the framework provides:

- A generic task runtime built around `TaskSubmission -> TaskRecord`
- A `TaskSupervisor` that validates inputs, resolves capabilities, executes them, and persists results
- A capability registry with built-in capability loading plus YAML-driven plugin loading
- Retry support via `max_retries`
- A local JSON-backed task store plus in-memory queue
- A `cond` CLI for local execution and inspection
- A workflow layer with planner/worker/validator interfaces and a synchronous `WorkflowOrchestrator`
- Optional long-term memory abstractions via `engine.interfaces.memory` and the memU-backed provider

## Built-In Runtime Capabilities

The packaged runtime exposes three built-ins by default. Verified locally with `cond 0.6.0`:

| Capability | Default | Risk | Tags | What it does |
|---|---|---|---|---|
| `echo` | yes | `low` | `testing`, `utility` | Returns a provided message unchanged. Useful for smoke tests, contract checks, and workflow examples. |
| `filesystem` | yes | `medium` | `io`, `local` | Reads files, writes files, and lists directory contents under a configured root path. |
| `http` | yes | `medium` | `network`, `api` | Performs simple outbound `GET` and `POST` requests and returns status + response text. |
| `memory` | optional plugin | `medium` | `memory`, `knowledge` | Persists and retrieves memory documents through the engine memory-provider abstraction. |

## Capability Details

### `echo`

- Input model: `message: str`
- Output: `{ "message": "<same message>" }`
- Main use: smoke tests, examples, verifying the runtime path without side effects

### `filesystem`

- Supported actions: `read_text`, `write_text`, `list_dir`
- Input fields:
  - `action`
  - `path`
  - `content` for writes
  - `encoding` defaulting to `utf-8`
- Guardrail: requested paths are validated against a configured base path before execution
- Main use: local document operations and deterministic file automation

### `http`

- Supported methods: `GET`, `POST`
- Input fields:
  - `method`
  - `url`
  - `headers`
  - `json_body`
  - `timeout_seconds`
- Output includes:
  - resolved URL
  - HTTP status code
  - raw response text
- Main use: calling simple APIs or fetching remote content without app-specific client code

### `memory`

- Not loaded by default in the shipped capability config
- Supports two actions:
  - `memorize`
  - `retrieve`
- Uses the engine memory contracts:
  - `MemoryDocument`
  - `MemoryQuery`
  - `MemoryHit`
  - `MemoryProvider`
- The current built-in implementation wraps `MemUProvider`
- Main use: reusable long-term memory integration for apps built on the engine

## Capability Loading Model

Conductor Engine keeps side effects behind capabilities. A capability exposes:

- metadata through `CapabilityDescriptor`
- input validation through `validate_input(...)`
- execution through `execute(payload, context)`

Capabilities are loaded in two ways:

1. Built-ins that ship with the engine
2. Plugins declared in YAML using Python import paths

Default config shape:

```yaml
include_builtins: true
capabilities: []
```

Example plugin entry:

```yaml
capabilities:
  - import_path: my_package.capabilities:CustomCapability
    config:
      api_base_url: https://example.internal
```

This is important for Home AI Control Plane because it means the generic execution surface can stay inside `conductor-engine`, while Home-specific skills and integrations can remain app-level or gradually become plugins.

## CLI and Operator Surface

The packaged CLI currently exposes:

- `cond run <task-file>`
- `cond capability list`
- `cond task list`
- `cond workflow run <workflow-file>`

That makes the framework usable on its own for local orchestration experiments, smoke tests, and contract verification.

## Workflow Layer

Above single-task execution, Conductor Engine also includes a workflow/orchestrator layer:

- `WorkflowGoal`
- `PlanStep`
- `WorkflowResult`
- `PlannerInterface`
- `WorkerInterface`
- `ValidatorInterface`
- `WorkflowOrchestrator`

The current workflow runtime is synchronous and sequential:

1. Planner produces ordered steps
2. Worker converts each step into a `TaskSubmission`
3. Supervisor executes the task through the capability registry
4. Validator assesses the final result

The shipped repo also includes simple reference agents:

- `LinearPlanner`
- `PassthroughWorker`
- `PassthroughValidator`

These are framework extension points rather than Home-specific intelligence. In other words, Conductor Engine already has a generic orchestration shell for multi-step execution, while Home AI Control Plane adds domain-specific planning, approval, and external-service coordination.

## What Home AI Control Plane Uses Today

Today this repo uses Conductor Engine mostly as a shared framework dependency rather than as the full runtime for every service.

Current direct integration points include:

- memory contracts from `engine.interfaces.memory`
- the memU-backed provider from `engine.memory.providers.memu`
- the published package dependency path rather than a sibling source checkout

That means Home AI Control Plane is already depending on the engine's reusable memory abstractions, while broader engine features such as the generic supervisor runtime, CLI, and workflow shell remain available for deeper adoption later.

## Research Notes

This summary was derived from:

- the published package version `0.6.0`
- the local sibling source repository at `../Conductor-Engine`
- capability implementations under `engine/capabilities/`
- capability config under `config/conductor.capabilities.yaml`
- framework docs under `docs/conductor/`

The most important practical distinction is:

- default packaged capabilities: `echo`, `filesystem`, `http`
- optional engine capability: `memory`
- broader framework features: registry/plugin loading, task supervision, retries, local store, CLI, and workflow orchestration
