from __future__ import annotations

from app.config import Settings
from app.tools.base import FaultInjector, ToolRegistry
from app.tools.github import make_catalog_tools, make_github_tools
from app.tools.logs import make_log_tools
from app.tools.mock_data import load_mock_data
from app.tools.retrieval import make_retrieval_tools
from app.tools.ticketing import IdempotentStore, make_action_tools


def build_tool_registry(settings: Settings, action_store: IdempotentStore) -> ToolRegistry:
    data = load_mock_data(settings.data_dir)
    specs = [
        *make_catalog_tools(data),
        *make_log_tools(data),
        *make_github_tools(data),
        *make_retrieval_tools(data),
        *make_action_tools(action_store),
    ]
    return ToolRegistry(
        specs,
        timeout_s=settings.tool_timeout_s,
        max_retries=settings.tool_max_retries,
        backoff_base_s=settings.tool_backoff_base_s,
        faults=FaultInjector(settings.fault_injection),
    )
