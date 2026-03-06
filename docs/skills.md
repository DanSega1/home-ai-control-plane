# Skills

## Overview

Skills are **not** Python code in this repo. Each skill lives in its own repository and is loaded dynamically at runtime:

1. `skills/registry.yaml` declares installed skills — source type, MCP server URL, auth config, and risk level.
2. On startup, `skill-runner` fetches the skill's `SKILL.md` from GitHub or skillstore.io and caches it locally.
3. At execution time, `SKILL.md` becomes the LLM system prompt; the MCP server exposes tools; the Skill Runner drives a tool-call loop until the instruction is complete.

## Installed Skills

| Skill ID | Name | Source | MCP Type | Risk |
|---|---|---|---|---|
| `raindrop-io` | Raindrop.io Bookmark Management | [DanSega1/raindrop-io-skill](https://github.com/DanSega1/raindrop-io-skill) `v1.0.0` | SSE | low (high for deletes) |

## `skills/registry.yaml` Format

```yaml
skills:
  <skill-id>:
    name: Human-readable name
    description: >
      What this skill does (shown in planner context).
    source:
      type: github          # github | skillstore | local
      repo: owner/repo      # for github
      ref: "v1.0.0"         # tag, branch, or commit SHA
      skill_file: SKILL.md  # defaults to SKILL.md if omitted
    mcp_server: "https://..."   # MCP server base URL
    mcp_type: sse               # sse | stdio
    version: "v1.0.0"
    tags: [tag1, tag2]
    risk_level: low             # default risk level for this skill
    requires_auth: true
    auth_env: ENV_VAR_NAME      # env var holding the Bearer token
```

### Source types

| Type | Description |
|---|---|
| `github` | Fetch `SKILL.md` from a GitHub repo. Set `repo`, `ref`, and optionally `skill_file`. Uses `GITHUB_TOKEN` env var for private repos. |
| `skillstore` | Fetch from skillstore.io by `skill_id`. |
| `local` | Load from a path relative to `skills/`. For development and testing only. |

## Adding a Skill

### 1. Add to `skills/registry.yaml`

Append a new entry following the format above. No code changes required.

### 2. Update the OPA skill policy

Edit `policies/homeai/skill/skill.rego` — add the skill to the `registry` and to `agent_skill_permissions`:

```rego
registry := {
  "raindrop-io": {"risk": "low", "destructive": true},
  "my-new-skill": {"risk": "low", "destructive": false},   # add this
}

agent_skill_permissions := {
  "planner":    {"raindrop-io", "my-new-skill"},            # add skill here
  "supervisor": {"raindrop-io", "my-new-skill"},            # and here
}
```

OPA hot-reloads the policy file — no restart needed.

### 3. Provide auth credentials (if required)

Add the auth env variable to `config/.env.skill-runner`:

```
MY_NEW_SKILL_TOKEN=your-token-here
```

And reference it as `auth_env: MY_NEW_SKILL_TOKEN` in `registry.yaml`.

### 4. Restart the Skill Runner

```bash
cd infra
docker compose restart skill-runner
```

The service fetches and caches `SKILL.md` on startup.

## How Execution Works

For each `ExecutionStep` in a plan:

1. The Skill Runner loads the cached `SKILL.md` for the step's `skill` ID.
2. It constructs an LLM prompt using `SKILL.md` as the system prompt and the step's `instruction` as the user message.
3. LiteLLM returns a response that may include MCP tool calls.
4. The Skill Runner dispatches each tool call to the MCP server and feeds results back.
5. The loop continues until the LLM produces a final answer (no more tool calls).
6. The output and token usage are recorded in the `TaskResult`.

Steps with `depends_on` entries wait until all dependency steps have completed. Circular dependencies are detected and reported as an error.

## `SKILL.md` Contract

A `SKILL.md` file is a Markdown document that functions as the LLM system prompt for the skill. It should describe:

- What the skill does
- Available MCP tools (name, parameters, purpose)
- Usage guidelines and constraints
- Examples

The Skill Runner passes it verbatim as the system message. The quality of `SKILL.md` directly affects execution quality.
