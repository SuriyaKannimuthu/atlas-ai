"""Deterministic authorization and action policies.

Nothing in this module consults a model. LLM output can *propose* actions, but whether a
caller may perform an operation, and whether an action needs human approval, is decided here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    APPROVER = "approver"
    ADMIN = "admin"


class Permission(StrEnum):
    INCIDENT_READ = "incident:read"
    INCIDENT_CREATE = "incident:create"
    INCIDENT_CANCEL = "incident:cancel"
    ACTION_APPROVE = "action:approve"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset({Permission.INCIDENT_READ}),
    Role.OPERATOR: frozenset(
        {Permission.INCIDENT_READ, Permission.INCIDENT_CREATE, Permission.INCIDENT_CANCEL}
    ),
    Role.APPROVER: frozenset({Permission.INCIDENT_READ, Permission.ACTION_APPROVE}),
    Role.ADMIN: frozenset(Permission),
}


@dataclass(frozen=True)
class Principal:
    subject: str
    role: Role

    def can(self, permission: Permission) -> bool:
        return permission in ROLE_PERMISSIONS[self.role]


# --- Remediation actions ---------------------------------------------------------------


class ActionRisk(StrEnum):
    LOW = "low"  # informational, reversible
    MEDIUM = "medium"  # externally visible, reversible
    HIGH = "high"  # production-impacting


@dataclass(frozen=True)
class ActionPolicy:
    action_type: str
    risk: ActionRisk
    requires_approval: bool
    tool: str
    description: str


ACTION_POLICIES: dict[str, ActionPolicy] = {
    "create_ticket": ActionPolicy(
        "create_ticket",
        ActionRisk.MEDIUM,
        requires_approval=True,
        tool="ticketing.create_ticket",
        description="Open a tracking ticket with the incident report attached.",
    ),
    "rollback_deployment": ActionPolicy(
        "rollback_deployment",
        ActionRisk.HIGH,
        requires_approval=True,
        tool="deploy.rollback",
        description="Roll the service back to the previous known-good deployment.",
    ),
    "notify_channel": ActionPolicy(
        "notify_channel",
        ActionRisk.LOW,
        requires_approval=False,
        tool="ticketing.notify",
        description="Post the incident summary to the owning team's channel.",
    ),
}


def classify_action(action_type: str) -> ActionPolicy | None:
    """Return the policy for a proposed action, or None if the action type is not allowed."""
    return ACTION_POLICIES.get(action_type)
