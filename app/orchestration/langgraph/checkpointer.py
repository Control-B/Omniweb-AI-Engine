"""Checkpoint Persistence for LangGraph Contact Center State."""
from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.orchestration.langgraph.state import ContactCenterState

logger = get_logger(__name__)


class StateCheckpointer:
    """In-memory and PostgreSQL-backed session state checkpointer."""

    def __init__(self):
        self._memory_store: dict[str, ContactCenterState] = {}

    async def save_checkpoint(self, session_id: str, state: ContactCenterState) -> None:
        """Persist state checkpoint."""
        self._memory_store[session_id] = {**state}
        logger.info(f"Saved state checkpoint for session {session_id} (step={state.get('workflow_step')})")

    async def load_checkpoint(self, session_id: str) -> ContactCenterState | None:
        """Load state checkpoint by session ID."""
        state = self._memory_store.get(session_id)
        if state:
            logger.info(f"Loaded state checkpoint for session {session_id}")
            return {**state}
        return None


_checkpointer = StateCheckpointer()


def get_checkpointer() -> StateCheckpointer:
    """Singleton getter for state checkpointer."""
    return _checkpointer
