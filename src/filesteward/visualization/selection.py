"""Display-only selection synchronization across navigator / map / inspector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from filesteward.models import CleanupDisposition
from filesteward.visualization.contracts import PresentationModel, PresentationNode

__all__ = ["SelectionController", "SelectionState"]


@dataclass
class SelectionState:
    """Mutable presentation selection. Never mutates node evidence."""

    selected_id: Optional[str]
    disposition_filter: Optional[CleanupDisposition] = None
    query: str = ""


@dataclass
class SelectionController:
    """Keeps list/map/inspector on one node_id.

    Call stack:
      select/filter/search -> recompute visible -> rebind selection if needed
    """

    model: PresentationModel
    state: SelectionState = field(init=False)

    def __post_init__(self) -> None:
        self.state = SelectionState(selected_id=self.model.default_selected_id)
        if self.state.selected_id is None and self.model.nodes:
            self.state.selected_id = self.model.nodes[0].node_id
        self._rebind_selection()

    def nodes_by_id(self) -> dict[str, PresentationNode]:
        return self.model.by_id()

    def visible_nodes(self) -> tuple[PresentationNode, ...]:
        query = self.state.query.casefold().strip()
        out: list[PresentationNode] = []
        for node in self.model.nodes:
            if (
                self.state.disposition_filter is not None
                and node.disposition is not self.state.disposition_filter
            ):
                continue
            if query and query not in node.path.casefold() and query not in node.display_name.casefold():
                continue
            out.append(node)
        return tuple(out)

    def visible_ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.visible_nodes())

    def select(self, node_id: str) -> SelectionState:
        if node_id not in self.nodes_by_id():
            raise KeyError(f"unknown presentation node_id: {node_id}")
        self.state.selected_id = node_id
        self._rebind_selection()
        return self.state

    def set_disposition_filter(
        self, disposition: CleanupDisposition | None
    ) -> SelectionState:
        self.state.disposition_filter = disposition
        self._rebind_selection()
        return self.state

    def set_query(self, query: str) -> SelectionState:
        self.state.query = query
        self._rebind_selection()
        return self.state

    def selected_node(self) -> Optional[PresentationNode]:
        if self.state.selected_id is None:
            return None
        return self.nodes_by_id().get(self.state.selected_id)

    def _rebind_selection(self) -> None:
        visible = self.visible_ids()
        if self.state.selected_id in visible:
            return
        self.state.selected_id = visible[0] if visible else None
