from __future__ import annotations

import copy
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


NODE_TYPES = {
    "Signal",
    "Question",
    "Thesis",
    "Variable",
    "Evidence",
    "Binding",
    "Relation",
    "Contradiction",
    "Entity",
    "Observation",
}

EDGE_TYPES = {
    "DERIVED_FROM",
    "SUPPORTED_BY",
    "BINDS",
    "CONTRADICTS",
    "REINFORCES",
    "REQUIRES",
    "OBSERVED_WITH",
    "RELATED_TO",
}

DAG_CONSTRAINED_EDGES = {"DERIVED_FROM", "SUPPORTED_BY"}


class KnowledgeGraphError(Exception):
    """Base exception for KnowledgeGraph operations."""


class CyclicProvenanceError(KnowledgeGraphError):
    """Raised when an edge creates a circular loop in an acyclic provenance DAG."""


@dataclass
class GraphNode:
    node_id: str
    node_type: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "data": copy.deepcopy(self.data),
            "created_at": self.created_at,
        }


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type,
            "metadata": copy.deepcopy(self.metadata),
            "created_at": self.created_at,
        }


class KnowledgeGraph:
    """
    Epistemic Knowledge Graph (v1.0):
    Maintains a multi-relational graph of signals, questions, open theses, variables, bindings, contradictions, and evidence.
    Enforces strict acyclicity on provenance edges (DERIVED_FROM, SUPPORTED_BY) with Fail-Closed semantics.
    """

    def __init__(self):
        self._nodes: dict[str, GraphNode] = {}
        self._out_edges: dict[str, list[GraphEdge]] = defaultdict(list)
        self._in_edges: dict[str, list[GraphEdge]] = defaultdict(list)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self._out_edges.values())

    def add_node(self, node_id: str, node_type: str, data: dict[str, Any] | None = None) -> GraphNode:
        if not node_id or not isinstance(node_id, str):
            raise ValueError(f"Invalid node_id: {node_id}")
        if node_type not in NODE_TYPES:
            raise ValueError(f"Invalid node_type: {node_type}. Must be one of {NODE_TYPES}")

        node = GraphNode(
            node_id=node_id,
            node_type=node_type,
            data=copy.deepcopy(data) if isinstance(data, dict) else {},
        )
        self._nodes[node_id] = node
        return node

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        metadata: dict[str, Any] | None = None,
        check_cycle: bool = True
    ) -> GraphEdge:
        if not self.has_node(source_id):
            raise ValueError(f"Source node '{source_id}' does not exist in graph.")
        if not self.has_node(target_id):
            raise ValueError(f"Target node '{target_id}' does not exist in graph.")
        if edge_type not in EDGE_TYPES:
            raise ValueError(f"Invalid edge_type: {edge_type}. Must be one of {EDGE_TYPES}")

        # Check self-loop on directed DAG edges
        if edge_type in DAG_CONSTRAINED_EDGES and source_id == target_id:
            raise CyclicProvenanceError(f"Self-referential provenance edge detected: {source_id} -> {target_id}")

        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            metadata=copy.deepcopy(metadata) if isinstance(metadata, dict) else {},
        )

        # Transitive Cycle Check for DAG edges (source -> target means source derives from target)
        if check_cycle and edge_type in DAG_CONSTRAINED_EDGES:
            if self._creates_cycle(source_id, target_id, edge_type):
                raise CyclicProvenanceError(
                    f"Adding edge {source_id} -[{edge_type}]-> {target_id} creates a circular dependency."
                )

        # Avoid duplicate parallel edges of same type
        for existing in self._out_edges[source_id]:
            if existing.target_id == target_id and existing.edge_type == edge_type:
                existing.metadata.update(edge.metadata)
                return existing

        self._out_edges[source_id].append(edge)
        self._in_edges[target_id].append(edge)
        return edge

    def _creates_cycle(self, source_id: str, target_id: str, edge_type: str) -> bool:
        """
        Returns True if traversing from target_id along edge_type edges reaches source_id.
        """
        visited = set()
        queue = deque([target_id])

        while queue:
            curr = queue.popleft()
            if curr == source_id:
                return True
            if curr in visited:
                continue
            visited.add(curr)

            for e in self._out_edges.get(curr, []):
                if e.edge_type == edge_type and e.target_id not in visited:
                    queue.append(e.target_id)

        return False

    def get_out_edges(self, node_id: str, edge_type: str | None = None) -> list[GraphEdge]:
        edges = self._out_edges.get(node_id, [])
        if edge_type:
            return [e for e in edges if e.edge_type == edge_type]
        return list(edges)

    def get_in_edges(self, node_id: str, edge_type: str | None = None) -> list[GraphEdge]:
        edges = self._in_edges.get(node_id, [])
        if edge_type:
            return [e for e in edges if e.edge_type == edge_type]
        return list(edges)

    def find_unconnected_signals(self) -> list[str]:
        """Finds signals that have zero outgoing or incoming relations/theses/questions."""
        unconnected = []
        for node_id, node in self._nodes.items():
            if node.node_type == "Signal":
                out_deg = len(self._out_edges.get(node_id, []))
                in_deg = len(self._in_edges.get(node_id, []))
                if out_deg == 0 and in_deg == 0:
                    unconnected.append(node_id)
        return sorted(unconnected)

    def find_incomplete_theses(self) -> list[dict[str, Any]]:
        """Finds open theses that still contain UNBOUND or CANDIDATE variables."""
        incomplete = []
        for node_id, node in self._nodes.items():
            if node.node_type == "Thesis":
                open_vars = node.data.get("open_variables", [])
                if isinstance(open_vars, list):
                    unbound_vars = [
                        v for v in open_vars
                        if isinstance(v, dict) and v.get("status") in ("UNBOUND", "CANDIDATE")
                    ]
                    if unbound_vars:
                        incomplete.append({
                            "thesis_id": node_id,
                            "hypothesis_template": node.data.get("hypothesis_template", ""),
                            "unbound_variables": unbound_vars,
                            "investigation_status": node.data.get("investigation_status", "OPEN"),
                        })
        return incomplete

    def find_contradictions(self) -> list[dict[str, Any]]:
        """Finds all active contradiction entities in the graph."""
        contradictions = []
        for node_id, node in self._nodes.items():
            if node.node_type == "Contradiction":
                contradictions.append(node.data)
        return contradictions

    def get_lineage(self, node_id: str) -> list[str]:
        """Returns the ancestor path for a node along DERIVED_FROM edges."""
        lineage = []
        visited = set()
        queue = deque([node_id])

        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)
            if curr != node_id:
                lineage.append(curr)

            for e in self.get_out_edges(curr, "DERIVED_FROM"):
                if e.target_id not in visited:
                    queue.append(e.target_id)

        return lineage

    def build_from_dataset(self, dataset_dict: dict[str, Any]) -> None:
        """Populates graph from a canonical or simulated knowledge state."""
        if not isinstance(dataset_dict, dict):
            return

        # 1. Add Signals
        for s in dataset_dict.get("signals", []):
            if isinstance(s, dict) and s.get("id"):
                self.add_node(s["id"], "Signal", s)

        # 2. Add Questions
        for q in dataset_dict.get("questions", []):
            if isinstance(q, dict) and q.get("id"):
                q_id = q["id"]
                self.add_node(q_id, "Question", q)
                # Link required signals
                for sig in q.get("required_signals", []):
                    if self.has_node(sig):
                        self.add_edge(q_id, sig, "REQUIRES")
                # Link provenance
                prov = q.get("provenance", {})
                for parent_id in prov.get("derived_from", []):
                    if self.has_node(parent_id):
                        try:
                            self.add_edge(q_id, parent_id, "DERIVED_FROM")
                        except CyclicProvenanceError:
                            pass

        # 3. Add Relations
        for r in dataset_dict.get("relations", []):
            if isinstance(r, dict) and r.get("id"):
                r_id = r["id"]
                self.add_node(r_id, "Relation", r)
                src = r.get("source_id")
                tgt = r.get("target_id")
                if src and tgt and self.has_node(src) and self.has_node(tgt):
                    rel_type = r.get("relation_type", "RELATED_TO")
                    edge_type = "REINFORCES" if rel_type == "REINFORCES" else "RELATED_TO"
                    self.add_edge(src, tgt, edge_type, {"relation_id": r_id})

        # 4. Add Open Theses
        for th in dataset_dict.get("open_theses", []):
            if isinstance(th, dict) and th.get("thesis_id"):
                th_id = th["thesis_id"]
                self.add_node(th_id, "Thesis", th)
                for sig in th.get("required_signals", []):
                    if self.has_node(sig):
                        self.add_edge(th_id, sig, "REQUIRES")

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [
                e.to_dict()
                for edge_list in self._out_edges.values()
                for e in edge_list
            ],
            "stats": {
                "node_count": self.node_count,
                "edge_count": self.edge_count,
            }
        }
