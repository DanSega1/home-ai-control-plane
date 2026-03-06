# Testing

## Overview

The test suite covers the shared contracts and the Supervisor service. Tests are pure-Python unit tests — no running Docker stack is required.

**Stack:** `pytest` + `pytest-asyncio` + `pytest-mock` + `httpx`

---

## Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing

# Run a specific file
pytest tests/contracts/test_task.py

# Run a specific test class or case
pytest tests/supervisor/test_task_service.py::TestExecuteTask
pytest tests/supervisor/test_task_service.py::TestExecuteTask::test_policy_denied_when_opa_rejects_task
```

`pytest` is configured in `pyproject.toml`:
- `testpaths = ["tests"]`
- `asyncio_mode = "auto"` — all async tests run without `@pytest.mark.asyncio`
- `pythonpath = ["."]` — project root is on `sys.path`, so `contracts.*` and `services.*` resolve correctly

---

## Test Layout

```
tests/
├── conftest.py              # shared fixtures (sample_step, sample_plan, sample_task, create_task_request)
├── contracts/
│   ├── test_task.py         # contracts/task.py — enums, models, serialization
│   └── test_model_usage.py  # contracts/model_usage.py — usage records, budget status
└── supervisor/
    ├── test_opa_client.py   # supervisor OPA HTTP client (mocked httpx)
    └── test_task_service.py # supervisor task orchestration logic (mocked DB + HTTP)
```

---

## Shared Fixtures (`tests/conftest.py`)

| Fixture | Type | Description |
|---|---|---|
| `sample_step` | `ExecutionStep` | A single low-risk `raindrop-io` step |
| `sample_plan` | `ExecutionPlan` | A high-tier, low-risk plan containing `sample_step` |
| `sample_task` | `Task` | An `APPROVED` task with `sample_plan` attached |
| `create_task_request` | `CreateTaskRequest` | A standard `HIGH`-tier creation request |

---

## `tests/contracts/test_task.py`

Unit tests for all models in `contracts/task.py`.

| Test class | What it covers |
|---|---|
| `TestTaskStatus` | All values are strings; terminal status set; default status is `PENDING` |
| `TestApprovalTier` | String values for all four tiers |
| `TestRiskLevel` | String values |
| `TestExecutionStep` | Defaults, auto-generated `step_id`, custom fields |
| `TestExecutionPlan` | Defaults, auto-generated `plan_id`, steps list, serialization roundtrip |
| `TestTask` | Defaults, auto-generated `task_id`, status mutation, audit trail, Notion page ID, serialization roundtrip |
| `TestTaskResult` | Success and failure shapes, defaults |
| `TestCreateTaskRequest` | Required fields, custom `approval_tier`, missing fields raise `ValueError` |
| `TestTaskStatusResponse` | Minimal and result-populated variants |

---

## `tests/contracts/test_model_usage.py`

Unit tests for `contracts/model_usage.py`.

| Test class | What it covers |
|---|---|
| `TestModelUsageRecord` | Defaults, auto-generated `record_id`, token counts, serialization roundtrip |
| `TestBudgetStatus` | Within-budget, exceeded by tokens, exceeded by cost, month format |

---

## `tests/supervisor/test_opa_client.py`

Tests for `services/supervisor/app/opa_client.py`. All HTTP calls are mocked with `unittest.mock.AsyncMock` + `patch("httpx.AsyncClient")`.

| Test class | What it covers |
|---|---|
| `TestEvaluate` | Allow response → `(True, True)`; deny → `(False, …)`; HTTP error → fail-closed `(False, None)`; missing `result` key → `False`; URL constructed correctly |
| `TestConvenienceWrappers` | `check_task_execution` calls `homeai/task/allow`; `check_budget` calls `homeai/budget/allow`; `check_skill_access` calls `homeai/skill/allow` |

**Fail-closed behaviour:** If OPA is unreachable (any `httpx` exception), `evaluate()` returns `(False, None)` — execution is denied, not allowed.

---

## `tests/supervisor/test_task_service.py`

Tests for `services/supervisor/app/services/task_service.py`. MongoDB and HTTP calls are fully mocked.

| Test class | What it covers |
|---|---|
| `TestGetBudgetStatus` | Zero usage when no records; aggregated tokens and cost from DB results; `budget_exceeded=True` when over token limit |
| `TestExecuteTask` | `ValueError` on unknown task; `ValueError` on non-approved task; `ValueError` on task with no plan; `POLICY_DENIED` when OPA rejects; `POLICY_DENIED` when budget OPA rejects |
| `TestCreateTask` | Task persisted to DB; status is `awaiting_approval` or `approved` after planning |

### Mocking pattern

Services are imported inside each test function to avoid module-level side effects (settings loading, DB connections). Patches target the `task_service` module's own references:

```python
with patch.object(task_service, "get_db", return_value=mock_db):
    ...
```

---

## Linting

Tests are linted with `ruff`. The `tests/**` path ignores annotation (`ANN`) and security (`S`) rules so tests stay readable without type annotations on every helper.

```bash
ruff check .
ruff format --check .
```

---

## What Is Not Yet Tested

The following are intentionally out of scope for the current test suite and are candidates for future coverage:

| Area | Notes |
|---|---|
| Planner agent | Requires mocking LiteLLM structured output |
| Skill Runner execution loop | Requires mocking MCP SSE client and LiteLLM tool-call loop |
| Notion Sync | Requires mocking Notion API |
| OPA policy logic | Can be tested with `opa test` against `.rego` files directly |
| Integration / end-to-end | Requires the full Docker stack; suitable for a separate `tests/integration/` suite |
