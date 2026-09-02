from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

StateT = TypeVar("StateT", bound=BaseModel)


class MockService(ABC, Generic[StateT]):
    """Base class for mock service state containers.

    Each concrete subclass owns its own typed Pydantic state model, seeded
    lazily via :meth:`_seed_state`. Replaces the previous pattern of a
    module-level `_STATE` dict plus parallel `get_state` / `reset_*` /
    `snapshot_state` functions in every mock package.
    """

    def __init__(self) -> None:
        self._state: StateT | None = None

    @abstractmethod
    def _seed_state(self) -> StateT:
        """Return a fresh seeded state model for this service."""

    def get_state(self) -> StateT:
        if self._state is None:
            self._state = self._seed_state()
        return self._state

    def reset(self) -> None:
        self._state = self._seed_state()

    def snapshot(self) -> StateT:
        return self.get_state().model_copy(deep=True)
