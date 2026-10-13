# Architecture

Atlas AI is two deployables in one repository:

| Path | What it is |
|---|---|
| `backend/` | FastAPI service that owns incidents, runs the LangGraph investigation workflow, enforces authorization and approval policy, and records the audit trail. |
| `frontend/` | Next.js (App Router) console. It holds the API key server-side and talks to the backend from Server Components, Server Actions, and one backend-for-frontend route. The browser never calls the backend directly. |

## Request flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant N as Next.js (server)
    participant A as FastAPI
    participant G as LangGraph worker
    participant DB as Postgres / SQLite

    B->>N: Submit form (Server Action)
    N->>A: POST /api/v1/incidents (X-API-Key)
    A->>DB: incident row (queued) + audit record
    A-->>N: 202 Accepted
    A->>G: dispatch on worker pool
    G->>DB: checkpoint after every step, workflow events
    B->>N: poll /api/incidents/{id} (BFF)
    N->>A: GET incident, events, report
    G-->>DB: interrupt -> approval request (awaiting_approval)
    B->>N: Approve (Server Action)
    N->>A: POST /approvals
    A->>G: resume from checkpoint with decision
    G->>DB: idempotent actions, final report (completed)
```

## Workflow graph

```mermaid
flowchart TD
    START((start)) --> triage
    triage --> plan
    plan -- "Send per plan step" --> log_analysis & code_analysis & knowledge_retrieval
    plan -- "empty plan" --> aggregate
    log_analysis --> aggregate
    code_analysis --> aggregate
    knowledge_retrieval --> aggregate
    aggregate --> review
    review -- "insufficient and budget left and a gap is closable" --> plan
    review -- "sufficient, or budget spent" --> report
    report --> policy_gate
    policy_gate -- "approval required" --> human_approval
    policy_gate -- "no approval required" --> execute_actions
    human_approval -- "interrupt(); resumed by API" --> execute_actions
    execute_actions --> END((end))
```

- **State** is a typed `IncidentState` (`backend/app/graph/state.py`). Evidence and completed steps use additive reducers so parallel branches merge; everything else has one owning node.
- **Run context** (tool registry, model gateway, event sink, budgets) is injected through LangGraph's runtime context and is never checkpointed.
- **Investigation branches degrade gracefully**: a tool failure marks the step failed and the review sees the gap, instead of the whole workflow failing.
- **Loop bound**: the planner never repeats a completed step and never runs more than one step per agent per round; `MAX_INVESTIGATION_ROUNDS` caps the loop.

## Where models are (and are not) used

| Component | Model use | Deterministic guard |
|---|---|---|
| Triage | Extracts category, symptoms, identifiers | Identifiers resolved against the catalog and deploy system; unknown values dropped |
| Planner | None | - |
| Log / code / knowledge agents | None (statistics, diffs, BM25) | Tool allowlists, argument schemas |
| Root-cause review | Refines hypotheses and confidence | Evidence IDs validated; sufficiency requires 2+ sources and corroboration |
| Reporting | Writes narrative fields | Structure, references, and proposed actions built in code |
| Approval and execution | None | Policy table + human approval + idempotency keys |

Without `MODEL_PROVIDER`/`MODEL_NAME` every agent runs its deterministic implementation, so the full platform (and CI) runs offline.

## Persistence

| Store | Contents |
|---|---|
| Application DB (SQLAlchemy; SQLite or Postgres) | incidents, workflow events, approval requests, audit records |
| Checkpointer (SQLite or Postgres) | LangGraph checkpoints per incident thread |
| Redis (optional) | shared rate-limit counters |

On startup the service resumes any incident left `queued` or `running` from its last checkpoint.

## Known limitations

- Integrations (logs, source control, deploys, ticketing) are mocks over `backend/data/`. Replace the tool implementations, not the agents, to connect real systems.
- Work runs on an in-process thread pool. Multiple API replicas would need a queue and a per-incident lock (Redis) to avoid double execution.
- Schema is created with `create_all`; there are no migrations yet.
- The Postgres checkpointer and Redis limiter code paths are not covered by the automated tests (they need running services).
