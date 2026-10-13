"""Source control and deployment metadata tools (mock GitHub / deploy system)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.tools.base import PermanentToolError, ToolSpec
from app.tools.mock_data import MockData, parse_ts


class DeploymentGetInput(BaseModel):
    deployment_id: str = Field(pattern=r"^d-\d{1,8}$")


class DeploymentListInput(BaseModel):
    service: str = Field(pattern=r"^[a-z0-9-]+$", max_length=64)
    before: datetime | None = None
    limit: int = Field(default=5, ge=1, le=20)


class CommitGetInput(BaseModel):
    sha: str = Field(pattern=r"^[0-9a-f]{7,40}$")


def make_github_tools(data: MockData) -> list[ToolSpec]:
    deployments = {row["id"]: row for row in data.deployments}
    commits = {row["sha"]: row for row in data.commits}

    def get_deployment(args: DeploymentGetInput) -> dict:
        if args.deployment_id not in deployments:
            raise PermanentToolError(f"deployment {args.deployment_id} not found")
        return deployments[args.deployment_id]

    def list_recent(args: DeploymentListInput) -> list[dict]:
        rows = [row for row in data.deployments if row["service"] == args.service]
        if args.before:
            rows = [row for row in rows if parse_ts(row["deployed_at"]) <= args.before]
        rows.sort(key=lambda row: row["deployed_at"], reverse=True)
        return rows[: args.limit]

    def get_commit(args: CommitGetInput) -> dict:
        if args.sha not in commits:
            raise PermanentToolError(f"commit {args.sha} not found")
        return commits[args.sha]

    return [
        ToolSpec(
            "deployments.get",
            "Fetch a deployment record by ID.",
            DeploymentGetInput,
            get_deployment,
        ),
        ToolSpec(
            "deployments.list_recent",
            "List recent deployments for a service.",
            DeploymentListInput,
            list_recent,
        ),
        ToolSpec(
            "github.get_commit",
            "Fetch a commit with its message, files, and diff.",
            CommitGetInput,
            get_commit,
        ),
    ]


def make_catalog_tools(data: MockData) -> list[ToolSpec]:
    class ListServicesInput(BaseModel):
        pass

    return [
        ToolSpec(
            "services.list",
            "List services in the service catalog.",
            ListServicesInput,
            lambda _args: data.services,
        )
    ]
