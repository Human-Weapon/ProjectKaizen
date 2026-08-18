from __future__ import annotations

import json

import pytest

from projectkaizen.exceptions import DuplicateError, ValidationError
from projectkaizen.graph import EdgeType, GraphEdge, GraphNode, ImprovementGraph, NodeType


def _basic_graph() -> ImprovementGraph:
    g = ImprovementGraph()
    g.add_node(GraphNode(id="a", type=NodeType.PROJECT_AREA))
    g.add_node(GraphNode(id="b", type=NodeType.FINDING))
    g.add_node(GraphNode(id="c", type=NodeType.IMPROVEMENT))
    return g


def test_add_node_and_duplicate_rejected():
    g = _basic_graph()
    with pytest.raises(DuplicateError):
        g.add_node(GraphNode(id="a", type=NodeType.PROJECT_AREA))


def test_add_edge_requires_existing_nodes():
    g = _basic_graph()
    with pytest.raises(ValidationError):
        g.add_edge(GraphEdge(source="zzz", type=EdgeType.AFFECTS, target="a"))
    with pytest.raises(ValidationError):
        g.add_edge(GraphEdge(source="b", type=EdgeType.AFFECTS, target="zzz"))


def test_add_edge_duplicate_rejected():
    g = _basic_graph()
    g.add_edge(GraphEdge(source="b", type=EdgeType.AFFECTS, target="a"))
    with pytest.raises(DuplicateError):
        g.add_edge(GraphEdge(source="b", type=EdgeType.AFFECTS, target="a"))


def test_nodes_and_edges_are_sorted_deterministically():
    g = ImprovementGraph()
    g.add_node(GraphNode(id="z", type=NodeType.FINDING))
    g.add_node(GraphNode(id="a", type=NodeType.FINDING))
    g.add_node(GraphNode(id="m", type=NodeType.FINDING))
    ids = [n.id for n in g.nodes()]
    assert ids == sorted(ids)


def test_nodes_filter_by_type():
    g = _basic_graph()
    findings = g.nodes(type=NodeType.FINDING)
    assert [n.id for n in findings] == ["b"]


def test_edges_from_and_to():
    g = _basic_graph()
    g.add_edge(GraphEdge(source="c", type=EdgeType.DEPENDS_ON, target="b"))
    assert [e.target for e in g.edges_from("c")] == ["b"]
    assert [e.source for e in g.edges_to("b")] == ["c"]
    assert g.edges_from("c", type=EdgeType.AFFECTS) == ()


def test_validate_reports_no_problems_on_healthy_graph():
    g = _basic_graph()
    g.add_edge(GraphEdge(source="b", type=EdgeType.AFFECTS, target="a"))
    assert g.validate() == ()


def test_detect_cycles_finds_simple_cycle():
    g = _basic_graph()
    g.add_edge(GraphEdge(source="a", type=EdgeType.DEPENDS_ON, target="b"))
    g.add_edge(GraphEdge(source="b", type=EdgeType.DEPENDS_ON, target="c"))
    g.add_edge(GraphEdge(source="c", type=EdgeType.DEPENDS_ON, target="a"))
    cycles = g.detect_cycles(EdgeType.DEPENDS_ON)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"a", "b", "c"}


def test_detect_cycles_none_when_acyclic():
    g = _basic_graph()
    g.add_edge(GraphEdge(source="a", type=EdgeType.DEPENDS_ON, target="b"))
    g.add_edge(GraphEdge(source="b", type=EdgeType.DEPENDS_ON, target="c"))
    assert g.detect_cycles(EdgeType.DEPENDS_ON) == ()


def test_detect_cycles_self_loop():
    g = _basic_graph()
    g.add_edge(GraphEdge(source="a", type=EdgeType.DEPENDS_ON, target="a"))
    cycles = g.detect_cycles(EdgeType.DEPENDS_ON)
    assert cycles == (("a",),)


def test_to_jsonable_roundtrip_is_deterministic():
    g = _basic_graph()
    g.add_edge(GraphEdge(source="b", type=EdgeType.AFFECTS, target="a", data={"weight": 1}))
    payload1 = g.to_jsonable()
    payload2 = g.to_jsonable()
    assert json.dumps(payload1, sort_keys=True) == json.dumps(payload2, sort_keys=True)

    restored = ImprovementGraph.from_jsonable(payload1)
    assert restored.to_jsonable() == payload1


def test_from_jsonable_rejects_bad_payload():
    with pytest.raises(ValidationError):
        ImprovementGraph.from_jsonable({"nodes": []})  # missing 'edges'
    with pytest.raises(ValidationError):
        ImprovementGraph.from_jsonable({"nodes": [{"id": "a", "type": "NOT_A_TYPE"}], "edges": []})
    with pytest.raises(ValidationError):
        ImprovementGraph.from_jsonable(
            {"nodes": [{"id": "a", "type": "FINDING"}], "edges": [{"source": "a", "type": "BOGUS", "target": "a"}]}
        )


def test_node_and_edge_construction_validation():
    with pytest.raises(ValidationError):
        GraphNode(id="", type=NodeType.FINDING)
    with pytest.raises(ValidationError):
        GraphNode(id="x", type="FINDING")  # not a NodeType
    with pytest.raises(ValidationError):
        GraphEdge(source="", type=EdgeType.AFFECTS, target="a")
    with pytest.raises(ValidationError):
        GraphEdge(source="a", type="AFFECTS", target="b")


def test_len_reflects_node_count():
    g = _basic_graph()
    assert len(g) == 3


def test_has_node_and_get_node():
    g = _basic_graph()
    assert g.has_node("a") is True
    assert g.has_node("zzz") is False
    assert g.get_node("a").id == "a"
    with pytest.raises(ValidationError):
        g.get_node("zzz")
