"""Replace node classes without coupling algorithms to their constructors."""

from abc import ABC, abstractmethod
from typing import Any

from .base import CaliTreeNode
from .node_leaf import CaliTreeLeafNode
from .node_merge import CaliTreeMergeNode


class NodeFactory(ABC):
    """Fields are the shared CaliTreeNode constructor keyword arguments."""

    @abstractmethod
    def leaf(self, **fields: Any) -> CaliTreeNode:
        ...

    @abstractmethod
    def merge(self, **fields: Any) -> CaliTreeNode:
        ...

    @abstractmethod
    def promoted_leaf(self, **fields: Any) -> CaliTreeNode:
        ...

    @abstractmethod
    def global_node(self, **fields: Any) -> CaliTreeNode:
        ...


class DefaultNodeFactory(NodeFactory):
    def leaf(self, **fields: Any) -> CaliTreeLeafNode:
        return CaliTreeLeafNode(**fields)

    def merge(self, **fields: Any) -> CaliTreeMergeNode:
        return CaliTreeMergeNode(**fields)

    def promoted_leaf(self, **fields: Any) -> CaliTreeLeafNode:
        return CaliTreeLeafNode(**fields)

    def global_node(self, **fields: Any) -> CaliTreeNode:
        return CaliTreeNode(**fields)
