# Threat model

Scope: the Atlas AI backend and frontend as shipped in this repository.

## Assets

- Ability to trigger external actions (tickets, notifications, **deployment rollbacks**).
- Incident data, logs, diffs, and reports, which can contain secrets or personal data.
- API keys and model-provider credentials.

## Threats and mitigations

| Threat | Mitigation | Where |
|---|---|---|
| Prompt injection via logs, commits, or documents steering the model into an action | Models cannot call side-effecting tools; only `action_executor` can, after the policy gate and human approval. Untrusted content is delimited in prompts and flagged in evidence and the report. | `security/untrusted.py`, `security/tool_access.py`, `agents/actions.py` |
| Hallucinated identifiers (service, deployment) redirecting the investigation | Triage resolves identifiers against the catalog/deploy system and drops unknown values. | `agents/triage.py` |
| Model claims unsupported by evidence | Evidence IDs returned by the model are validated; hypotheses without grounded evidence are dropped; sufficiency is a deterministic gate. | `agents/root_cause_review.py` |
| Unauthorized callers or privilege misuse | API keys mapped to roles with least-privilege permissions; constant-time key comparison; optional separation of duties for approvals. | `api/dependencies.py`, `security/policy.py` |
| Duplicate or replayed external actions after retries or restarts | Idempotency key per incident and action; approval decisions recorded with a conditional update. | `tools/ticketing.py`, `persistence/repository.py` |
| Runaway cost or loops | Round cap, tool-call budget, per-tool timeouts, workflow time budget, rate limiting. | `config.py`, `tools/base.py`, `graph/context.py` |
| Secrets leaking into events, audit, or traces | Recursive redaction before events and audit records are stored. | `security/redaction.py` |
| Malformed tool arguments | Pydantic schemas with patterns and bounds on every tool input. | `tools/*.py` |
| API key exposure in the browser | The key lives only in the Next.js server environment; the browser talks to Next.js. | `frontend/src/lib/atlas.ts` |

## Residual risks

- The development fallback key (`atlas-dev-key`) grants admin when `API_KEYS` is empty and `APP_ENV=development`. Production refuses to start without keys.
- Injection detection is pattern-based and will miss novel phrasing. It is a signal, not a control; the controls are the tool allowlist and approval gate.
- LangSmith traces include model inputs. Event redaction does not apply to traces sent by LangChain; disable tracing or configure LangSmith redaction for sensitive environments.
- Mock integrations do not exercise real credential handling.
