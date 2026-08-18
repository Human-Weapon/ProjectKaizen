"""ImprovementGraph: an explicit, validated, deterministic graph of
improvement-related entities.

Node ids are caller-supplied (deterministic — derived from content, not
randomness or timestamps). Edge ids are derived deterministically from
(source, type, target), so the same logical edge added twice is a duplicate,
not a data structure with unstable identity.

Cycles are not silently rejected: DEPENDS_ON cycles are detected and
reported via ``detect_cycles`` rather than raised, since a caller may want to
surface them as a finding instead of crashing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from .exceptions import DuplicateError, ValidationError
from .jsonutil import to_jsonable
from .numbers import require_nonblank_str


class NodeType(str, Enum):
    PROJECT_AREA = "PROJECT_AREA"
    FINDING = "FINDING"
    ROOT_CAUSE = "ROOT_CAUSE"
    IMPROVEMENT = "IMPROVEMENT"
    DEPENDENCY = "DEPENDENCY"
    EVIDENCE = "EVIDENCE"
    OUTCOME = "OUTCOME"
    LESSON = "LESSON"


class EdgeType(str, Enum):
    AFFECTS = "AFFECTS"
    CAUSED_BY = "CAUSED_BY"
    IMPROVED_BY = "IMPROVED_BY"
    DEPENDS_ON = "DEPENDS_ON"
    VALIDATED_BY = "VALIDATED_BY"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    SUPERSEDES = "SUPERSEDES"
    RESULTED_IN = "RESULTED_IN"
    LEARNED_FROM = "LEARNED_FROM"


def _freeze_data(data: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if data is None:
        return MappingProxyType({})
    if not isinstance(data, Mapping):
        raise ValidationError("node/edge data must be a mapping")
    return MappingProxyType(dict(data))


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: str
    type: NodeType
    data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="node.id"))
        if not isinstance(self.type, NodeType):
            raise ValidationError("node.type must be a NodeType")
        object.__setattr__(self, "data", _freeze_data(self.data))

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "data": to_jsonable(dict(self.data), name=f"node[{self.id}].data"),
        }


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    type: EdgeType
    target: str
    data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", require_nonblank_str(self.source, name="edge.source"))
        object.__setattr__(self, "target", require_nonblank_str(self.target, name="edge.target"))
        if not isinstance(self.type, EdgeType):
            raise ValidationError("edge.type must be an EdgeType")
        object.__setattr__(self, "data", _freeze_data(self.data))

    @property
    def id(self) -> str:
        return f"{self.source}::{self.type.value}::{self.target}"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "type": self.type.value,
            "target": self.target,
            "data": to_jsonable(dict(self.data), name=f"edge[{self.id}].data"),
        }


class ImprovementGraph:
    """A validated, append-mostly graph.

    Nodes and edges are immutable once added. Edges may never reference a
    node that does not exist (no dangling edges) — this is enforced at
    insertion time, not deferred to a later validation pass.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._out: dict[str, list[str]] = {}
        self._in: dict[str, list[str]] = {}

    def add_node(self, node: GraphNode) -> None:
        if node.id in self._nodes:
            raise DuplicateError(f"node id already exists: {node.id!r}")
        self._nodes[node.id] = node
        self._out.setdefault(node.id, [])
        self._in.setdefault(node.id, [])

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.source not in self._nodes:
            raise ValidationError(f"edge source node does not exist: {edge.source!r}")
        if edge.target not in self._nodes:
            raise ValidationError(f"edge target node does not exist: {edge.target!r}")
        if edge.id in self._edges:
            raise DuplicateError(f"edge already exists: {edge.id!r}")
        self._edges[edge.id] = edge
        self._out[edge.source].append(edge.id)
        self._in[edge.target].append(edge.id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> GraphNode:
        try:
            return self._nodes[node_id]
        except KeyError:
            raise ValidationError(f"unknown node id: {node_id!r}") from None

    def nodes(self, *, type: NodeType | None = None) -> tuple[GraphNode, ...]:
        values = self._nodes.values()
        if type is not None:
            values = (n for n in values if n.type == type)
        return tuple(sorted(values, key=lambda n: n.id))

    def edges(self, *, type: EdgeType | None = None) -> tuple[GraphEdge, ...]:
        values = self._edges.values()
        if type is not None:
            values = (e for e in values if e.type == type)
        return tuple(sorted(values, key=lambda e: (e.type.value, e.source, e.target)))

    def edges_from(self, node_id: str, *, type: EdgeType | None = None) -> tuple[GraphEdge, ...]:
        ids = self._out.get(node_id, [])
        result = (self._edges[i] for i in ids)
        if type is not None:
            result = (e for e in result if e.type == type)
        return tuple(sorted(result, key=lambda e: (e.type.value, e.target)))

    def edges_to(self, node_id: str, *, type: EdgeType | None = None) -> tuple[GraphEdge, ...]:
        ids = self._in.get(node_id, [])
        result = (self._edges[i] for i in ids)
        if type is not None:
            result = (e for e in result if e.type == type)
        return tuple(sorted(result, key=lambda e: (e.type.value, e.source)))

    def validate(self) -> tuple[str, ...]:
        """Re-validate structural invariants. Returns a tuple of problems.

        Since dangling edges are prevented at insertion time, an empty
        result is the expected steady state; this exists as a defensive
        double-check (e.g. after deserialization) rather than the primary
        enforcement mechanism.
        """
        problems: list[str] = []
        for edge in self.edges():
            if edge.source not in self._nodes:
                problems.append(f"dangling edge source: {edge.id}")
            if edge.target not in self._nodes:
                problems.append(f"dangling edge target: {edge.id}")
        return tuple(problems)

    def detect_cycles(self, edge_type: EdgeType) -> tuple[tuple[str, ...], ...]:
        """Return cycles among edges of ``edge_type`` as tuples of node ids.

        Deterministic: neighbors are visited in sorted node-id order, and
        each distinct cycle is reported once, rooted at its lexicographically
        smallest node.
        """
        adjacency: dict[str, list[str]] = {n: [] for n in self._nodes}
        for edge in self.edges(type=edge_type):
            adjacency[edge.source].append(edge.target)
        for key in adjacency:
            adjacency[key].sort()

        cycles: list[tuple[str, ...]] = []
        seen_cycle_keys: set[frozenset[str]] = set()
        WHITE, GRAY, BLACK = 0, 1, 2
        color = dict.fromkeys(self._nodes, WHITE)

        def dfs(start: str) -> None:
            stack: list[tuple[str, int]] = [(start, 0)]
            path: list[str] = []
            while stack:
                node, i = stack[-1]
                if i == 0:
                    color[node] = GRAY
                    path.append(node)
                neighbors = adjacency[node]
                if i < len(neighbors):
                    stack[-1] = (node, i + 1)
                    nxt = neighbors[i]
                    if color[nxt] == WHITE:
                        stack.append((nxt, 0))
                    elif color[nxt] == GRAY:
                        idx = path.index(nxt)
                        cycle = tuple(path[idx:])
                        key = frozenset(cycle)
                        if key not in seen_cycle_keys:
                            seen_cycle_keys.add(key)
                            min_idx = cycle.index(min(cycle))
                            cycles.append(cycle[min_idx:] + cycle[:min_idx])
                else:
                    color[node] = BLACK
                    path.pop()
                    stack.pop()

        for node_id in sorted(self._nodes):
            if color[node_id] == WHITE:
                dfs(node_id)

        cycles.sort()
        return tuple(cycles)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_jsonable() for n in self.nodes()],
            "edges": [e.to_jsonable() for e in self.edges()],
        }

    @classmethod
    def from_jsonable(cls, data: Mapping[str, Any]) -> ImprovementGraph:
        if not isinstance(data, Mapping) or "nodes" not in data or "edges" not in data:
            raise ValidationError("graph payload must have 'nodes' and 'edges'")
        graph = cls()
        for raw_node in data["nodes"]:
            if not isinstance(raw_node, Mapping):
                raise ValidationError("graph node entries must be objects")
            try:
                node_type = NodeType(raw_node["type"])
            except (KeyError, ValueError) as exc:
                raise ValidationError(f"invalid node type: {raw_node.get('type')!r}") from exc
            graph.add_node(GraphNode(id=raw_node["id"], type=node_type, data=raw_node.get("data") or {}))
        for raw_edge in data["edges"]:
            if not isinstance(raw_edge, Mapping):
                raise ValidationError("graph edge entries must be objects")
            try:
                edge_type = EdgeType(raw_edge["type"])
            except (KeyError, ValueError) as exc:
                raise ValidationError(f"invalid edge type: {raw_edge.get('type')!r}") from exc
            graph.add_edge(
                GraphEdge(
                    source=raw_edge["source"],
                    type=edge_type,
                    target=raw_edge["target"],
                    data=raw_edge.get("data") or {},
                )
            )
        return graph

    def __len__(self) -> int:
        return len(self._nodes)
