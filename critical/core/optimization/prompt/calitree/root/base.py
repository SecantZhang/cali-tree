"""Root selection contract."""

from abc import ABC, abstractmethod

from ..context import BuildContext, RootSelection


class RootSelector(ABC):
    @abstractmethod
    def select(self, context: BuildContext, *, accepted_merges: int) -> RootSelection:
        """Select the fallback prompt; record validation events in the context."""
        ...
