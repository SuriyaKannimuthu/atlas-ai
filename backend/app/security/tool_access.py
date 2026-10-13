"""Least-privilege tool access: which workflow component may call which tool."""

from __future__ import annotations

AGENT_TOOL_ALLOWLIST: dict[str, frozenset[str]] = {
    "triage": frozenset({"services.list", "deployments.list_recent"}),
    "log_analysis": frozenset({"logs.search", "deployments.get"}),
    "code_analysis": frozenset({"deployments.get", "deployments.list_recent", "github.get_commit"}),
    "knowledge_retrieval": frozenset({"knowledge.search"}),
    # Only the action executor may call tools with external side effects, and it only runs
    # after the deterministic approval gate.
    "action_executor": frozenset(
        {"ticketing.create_ticket", "ticketing.notify", "deploy.rollback"}
    ),
}


def is_tool_allowed(caller: str, tool_name: str) -> bool:
    return tool_name in AGENT_TOOL_ALLOWLIST.get(caller, frozenset())
