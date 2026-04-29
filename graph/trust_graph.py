"""
Trust Graph Construction Module

This module builds a directed graph of financial relationships:
- Users (borrowers)
- Landlords (property owners)
- Merchants (shops, businesses)
- Transaction edges (with frequency and trust weights)

The graph is the foundation for:
1. PageRank centrality scoring (transitive trust)
2. Sybil detection (graph structure analysis)
3. Spatial graph neural network (GINEConv) embeddings

The graph respects financial physics:
- Users can only borrow, not lend
- Landlords are anchors (external trust signal)
- Merchant density varies by location
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class NodeFeatures:
    """
    Feature vector for a node in the trust graph.

    These features are used by GNN models for credit scoring.

    Attributes:
        node_id: Unique identifier
        node_type: "user", "landlord", or "merchant"
        income_volatility_index: 0-1 (0=stable, 1=highly volatile)
        expense_to_income_ratio: 0-... (0=no expenses, 1=break-even)
        merchant_density_score: 0-1 (how many unique merchants)
        transaction_count: Total outgoing transactions
        average_transaction_value: Average amount per transaction
        axiom_score: Credit score if this node is a landlord (external signal)
        metadata: Additional attributes
    """

    node_id: str
    node_type: str  # "user", "landlord", "merchant"
    income_volatility_index: float = 0.0
    expense_to_income_ratio: float = 0.0
    merchant_density_score: float = 0.0
    transaction_count: int = 0
    average_transaction_value: float = 0.0
    axiom_score: float | None = None  # For landlord nodes
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_vector(self) -> list[float]:
        """
        Convert to feature vector for GNN input.

        Returns:
            List of 8 numerical features in consistent order
        """
        return [
            self.income_volatility_index,
            self.expense_to_income_ratio,
            self.merchant_density_score,
            float(self.transaction_count),
            self.average_transaction_value,
            self.axiom_score if self.axiom_score else 0.0,
            1.0 if self.node_type == "user" else 0.0,
            1.0 if self.node_type == "landlord" else 0.0,
        ]


@dataclass
class EdgeFeatures:
    """
    Features of a transaction edge in the trust graph.

    Attributes:
        src: Source node (payer)
        dst: Destination node (payee)
        frequency: "daily", "weekly", "monthly", or "sporadic"
        total_volume: Total amount transferred
        avg_amount: Average per-transaction amount
        transaction_count: Number of transactions
        trust_weight: 0-1 score (higher = more trustworthy relationship)
        metadata: Additional attributes
    """

    src: str
    dst: str
    frequency: str
    total_volume: float
    avg_amount: float
    transaction_count: int
    trust_weight: float
    metadata: dict[str, Any] = field(default_factory=dict)


class TrustGraph(nx.DiGraph):
    """
    Directed graph of financial trust relationships.

    This is the core data structure for Axiom credit scoring. It models:

    1. **Nodes**: Users (borrowers), landlords (external anchors), merchants
    2. **Edges**: UPI transactions with trust weights
    3. **Features**: Each node carries a feature vector for GNN
    4. **Constraints**: Financial physics (users can't lend, only borrow)

    Example:
        >>> graph = TrustGraph()
        >>> graph.add_user("user123", features={"income": 50000})
        >>> graph.add_landlord("landlord456", axiom_score=700)
        >>> graph.add_transaction_edge(
        ...     "user123", "landlord456", freq="monthly", amount=10000, trust=0.9
        ... )
        >>> pr = graph.compute_pagerank()
        >>> print(pr["user123"])  # User's centrality score

    All node IDs must be globally unique. Node types are strict:
    - "user": Borrower (thin-file individual)
    - "landlord": Property owner (external anchor)
    - "merchant": Business (utility/shop)
    """

    def __init__(self) -> None:
        """Initialize an empty trust graph."""
        super().__init__()
        self.node_features: dict[str, NodeFeatures] = {}
        self.edge_features: dict[tuple, EdgeFeatures] = {}
        logger.info("Initialized TrustGraph")

    def add_user(
        self,
        user_id: str,
        features: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a user (borrower) node to the graph.

        Users are sinks in the graph (they borrow, don't lend).
        If a user sends money to another user, the receiving user is treated as
        a merchant/service provider.

        Args:
            user_id: Unique user identifier
            features: Dictionary with optional keys:
                - income_volatility_index
                - expense_to_income_ratio
                - merchant_density_score
                - transaction_count
                - average_transaction_value

        Raises:
            ValueError: If user_id already exists as a different node type
        """
        if user_id in self.nodes:
            node_type = self.nodes[user_id].get("node_type")
            if node_type and node_type != "user":
                raise ValueError(
                    f"Node {user_id} already exists as {node_type}, cannot add as user"
                )

        # Create feature vector
        features = features or {}
        node_features = NodeFeatures(
            node_id=user_id,
            node_type="user",
            income_volatility_index=float(features.get("income_volatility_index", 0.0)),
            expense_to_income_ratio=float(features.get("expense_to_income_ratio", 0.0)),
            merchant_density_score=float(features.get("merchant_density_score", 0.0)),
            transaction_count=int(features.get("transaction_count", 0)),
            average_transaction_value=float(
                features.get("average_transaction_value", 0.0)
            ),
            metadata=features.get("metadata", {}),
        )

        # Add to NetworkX graph
        self.add_node(
            user_id,
            node_type="user",
            features=node_features.to_vector(),
            feature_obj=node_features,
        )
        self.node_features[user_id] = node_features

        logger.debug(f"Added user node: {user_id}")

    def add_landlord(
        self,
        landlord_id: str,
        axiom_score: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a landlord (external anchor) node to the graph.

        Landlords represent trusted external sources of validation:
        - Their Axiom scores (if already scored) act as transitive trust signals
        - A tenant with a high-score landlord inherits trust

        Args:
            landlord_id: Unique landlord identifier
            axiom_score: 300-900 Axiom score of the landlord
            metadata: Additional metadata (address, property count, etc.)

        Raises:
            ValueError: If axiom_score outside 300-900 range
            ValueError: If landlord_id already exists as a different node type
        """
        if not (300 <= axiom_score <= 900):
            raise ValueError(f"axiom_score must be in [300, 900], got {axiom_score}")

        if landlord_id in self.nodes:
            node_type = self.nodes[landlord_id].get("node_type")
            if node_type and node_type != "landlord":
                raise ValueError(
                    f"Node {landlord_id} already exists as {node_type}, "
                    f"cannot add as landlord"
                )

        node_features = NodeFeatures(
            node_id=landlord_id,
            node_type="landlord",
            axiom_score=axiom_score,
            metadata=metadata or {},
        )

        self.add_node(
            landlord_id,
            node_type="landlord",
            axiom_score=axiom_score,
            features=node_features.to_vector(),
            feature_obj=node_features,
        )
        self.node_features[landlord_id] = node_features

        logger.debug(f"Added landlord node: {landlord_id} (score={axiom_score})")

    def add_merchant(
        self,
        merchant_id: str,
        gst_registered: bool = False,
        category: str = "general",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a merchant (business) node to the graph.

        Merchants are utilities (electricity company), shops, restaurants, etc.

        Args:
            merchant_id: Unique merchant identifier
            gst_registered: Whether merchant is officially registered
            category: Merchant category (e.g., "utility", "retail", "food")
            metadata: Additional metadata

        Raises:
            ValueError: If merchant_id already exists as a different node type
        """
        if merchant_id in self.nodes:
            node_type = self.nodes[merchant_id].get("node_type")
            if node_type and node_type != "merchant":
                raise ValueError(
                    f"Node {merchant_id} already exists as {node_type}, "
                    f"cannot add as merchant"
                )

        node_features = NodeFeatures(
            node_id=merchant_id,
            node_type="merchant",
            metadata={"gst_registered": gst_registered, "category": category, 
                      **(metadata or {})},
        )

        self.add_node(
            merchant_id,
            node_type="merchant",
            gst_registered=gst_registered,
            category=category,
            features=node_features.to_vector(),
            feature_obj=node_features,
        )
        self.node_features[merchant_id] = node_features

        logger.debug(f"Added merchant node: {merchant_id} (category={category})")

    def add_transaction_edge(
        self,
        src: str,
        dst: str,
        frequency: str,
        total_volume: float,
        avg_amount: float | None = None,
        transaction_count: int = 1,
        trust_weight: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a transaction edge between two nodes.

        Represents a flow of money from src to dst. Multiple calls with the same
        (src, dst) pair will update the edge (merge transaction data).

        Args:
            src: Source node ID (payer)
            dst: Destination node ID (payee)
            frequency: "daily", "weekly", "monthly", "sporadic"
            total_volume: Total amount transferred
            avg_amount: Average per-transaction amount (if None, calculated)
            transaction_count: Number of transactions
            trust_weight: 0-1 confidence in this relationship
            metadata: Additional edge metadata

        Raises:
            ValueError: If nodes don't exist
            ValueError: If trust_weight outside [0, 1]

        Note:
            - Edges must connect existing nodes
            - trust_weight combines frequency, consistency, and legitimacy
        """
        if src not in self.nodes:
            raise ValueError(f"Source node {src} does not exist")
        if dst not in self.nodes:
            raise ValueError(f"Destination node {dst} does not exist")

        if not (0.0 <= trust_weight <= 1.0):
            raise ValueError(f"trust_weight must be in [0, 1], got {trust_weight}")

        # Calculate avg_amount if not provided
        if avg_amount is None:
            avg_amount = total_volume / transaction_count if transaction_count > 0 else 0.0

        edge_features = EdgeFeatures(
            src=src,
            dst=dst,
            frequency=frequency,
            total_volume=total_volume,
            avg_amount=avg_amount,
            transaction_count=transaction_count,
            trust_weight=trust_weight,
            metadata=metadata or {},
        )

        # Add edge to graph
        self.add_edge(
            src,
            dst,
            weight=trust_weight,  # NetworkX uses 'weight' for algorithms
            frequency=frequency,
            total_volume=total_volume,
            avg_amount=avg_amount,
            transaction_count=transaction_count,
            edge_features=edge_features,
        )

        self.edge_features[(src, dst)] = edge_features

        logger.debug(
            f"Added transaction edge: {src} -> {dst} "
            f"(frequency={frequency}, volume={total_volume}, trust={trust_weight})"
        )

    def compute_pagerank(self, alpha: float = 0.85, max_iter: int = 100) -> dict[str, float]:
        """
        Compute PageRank centrality scores for all nodes.

        PageRank models the transitive trust: a user who receives money from
        high-centrality peers is themselves more trustworthy.

        Args:
            alpha: Damping factor (0.85 standard; higher = trust in graph more)
            max_iter: Maximum iterations for convergence

        Returns:
            Dictionary mapping node_id -> centrality_score in [0, 1]

        Note:
            - Converges PageRank to normalize: sum of all scores = 1.0
            - High-centrality merchants inflate user scores (economic hubs)
            - High-centrality users inflate merchant scores (legitimate business)
        """
        if len(self.nodes) == 0:
            logger.warning("PageRank on empty graph")
            return {}

        try:
            # Compute PageRank using NetworkX
            pagerank = nx.pagerank(self, alpha=alpha, max_iter=max_iter)

            # Normalize to [0, 1] range
            if pagerank:
                max_pr = max(pagerank.values())
                if max_pr > 0:
                    pagerank = {node: score / max_pr for node, score in pagerank.items()}

            logger.info(f"Computed PageRank for {len(pagerank)} nodes")
            return pagerank

        except nx.NetworkXError as e:
            logger.error(f"Error computing PageRank: {e}")
            return {node: 0.5 for node in self.nodes}  # Fallback

    def get_node_features_matrix(self) -> tuple[list[str], list[list[float]]]:
        """
        Extract all node IDs and their feature vectors.

        Used for GNN model input.

        Returns:
            Tuple of (node_ids, feature_matrix) where:
            - node_ids: List of node IDs (preserves order)
            - feature_matrix: List of feature vectors, same length
        """
        node_ids = list(self.nodes)
        features = [
            self.node_features[node_id].to_vector() for node_id in node_ids
        ]
        return node_ids, features

    def get_edge_index_and_attributes(
        self,
    ) -> tuple[list[tuple[int, int]], list[list[float]]]:
        """
        Extract edge list and attributes for GNN.

        Converts node IDs to indices for PyTorch Geometric compatibility.

        Returns:
            Tuple of (edge_index, edge_attributes) where:
            - edge_index: List of (src_idx, dst_idx) tuples
            - edge_attributes: List of edge feature vectors
        """
        node_ids = list(self.nodes)
        node_to_idx = {node_id: i for i, node_id in enumerate(node_ids)}

        edge_index = []
        edge_attrs = []

        for src, dst, data in self.edges(data=True):
            src_idx = node_to_idx[src]
            dst_idx = node_to_idx[dst]
            edge_index.append((src_idx, dst_idx))

            # Create edge attribute vector [weight, frequency_encoded]
            frequency_encoding = {
                "daily": 3.0,
                "weekly": 2.0,
                "monthly": 1.0,
                "sporadic": 0.0,
            }
            weight = data.get("weight", 0.5)
            freq = frequency_encoding.get(data.get("frequency", "sporadic"), 0.0)
            edge_attrs.append([weight, freq])

        return edge_index, edge_attrs

    def get_connected_component_stats(self) -> dict[str, Any]:
        """
        Compute statistics about graph connectivity.

        Returns:
            Dictionary with metrics like:
            - num_connected_components
            - largest_component_size
            - avg_degree
            - density
        """
        if self.number_of_nodes() == 0:
            return {}

        return {
            "num_nodes": self.number_of_nodes(),
            "num_edges": self.number_of_edges(),
            "density": nx.density(self),
            "avg_degree": sum(dict(self.degree()).values()) / self.number_of_nodes(),
            "num_connected_components": nx.number_weakly_connected_components(self),
        }
