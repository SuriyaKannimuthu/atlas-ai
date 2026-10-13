"""Checkpointer factory. Checkpoints are what make investigations resumable."""

from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager, ExitStack
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from app.config import Settings


def open_checkpointer(settings: Settings, stack: ExitStack) -> BaseCheckpointSaver:
    """Create the configured checkpointer; resources are released when `stack` closes."""
    if settings.checkpointer == "memory":
        return InMemorySaver()

    if settings.checkpointer == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver

        path = Path(settings.checkpoint_url)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        stack.callback(conn.close)
        saver = SqliteSaver(conn)
        saver.setup()
        return saver

    from langgraph.checkpoint.postgres import PostgresSaver

    manager: AbstractContextManager[PostgresSaver] = PostgresSaver.from_conn_string(
        settings.checkpoint_url
    )
    saver = stack.enter_context(manager)
    saver.setup()
    return saver
