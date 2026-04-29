"""
Test Suite for Graph Module

Tests for trust graph construction, KDTree enrichment, and neural models.
"""

import pytest
import torch
import networkx as nx

from graph.trust_graph import TrustGraph, NodeFeatures, EdgeFeatures
from graph.kdtree_enricher import KDTreeEnricher
from graph.gineconv_model import GINEConv
from graph.gru_temporal import GRUTemporal
from graph.st_pignn import STPIGNNFusion


@pytest.fixture
def trust_graph():
    """Initialize trust graph for testing."""
    g = TrustGraph()
    g.add_user("user1", features={"income_volatility_index": 0.3})
    g.add_merchant("merchant1", category="retail")
    return g


def test_trust_graph_add_user(trust_graph):
    """Test adding user to graph."""
    assert "user1" in trust_graph.nodes()
    assert trust_graph.nodes["user1"]["node_type"] == "user"


def test_trust_graph_add_transaction_edge(trust_graph):
    """Test adding transaction edge."""
    trust_graph.add_transaction_edge(
        "user1",
        "merchant1",
        frequency="daily",
        total_volume=5000.0,
        avg_amount=100.0,
        transaction_count=50,
        trust_weight=0.8,
    )
    assert ("user1", "merchant1") in trust_graph.edges()


def test_trust_graph_pagerank(trust_graph):
    """Test PageRank computation."""
    trust_graph.add_transaction_edge(
        "user1",
        "merchant1",
        frequency="daily",
        total_volume=5000.0,
        avg_amount=100.0,
        transaction_count=50,
        trust_weight=0.8,
    )
    pagerank = trust_graph.compute_pagerank()
    assert isinstance(pagerank, dict)
    assert "user1" in pagerank


def test_kdtree_enricher_initialization():
    """Test KDTree enricher initialization."""
    enricher = KDTreeEnricher()
    assert enricher is not None


def test_gineconv_forward_pass():
    """Test GINEConv spatial embedding."""
    gineconv = GINEConv()
    x = torch.randn(5, 8)  # 5 nodes, 8 features
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]])
    edge_attr = torch.randn(3, 2)

    embeddings = gineconv(x, edge_index, edge_attr)
    assert embeddings.shape == (5, 64)  # Output dimension


def test_gru_temporal_forward_pass():
    """Test GRU temporal embedding."""
    gru = GRUTemporal()
    x = torch.randn(4, 12, 8)  # 4 users, 12 months, 8 features
    embeddings = gru(x)
    assert embeddings.shape == (4, 64)  # Output dimension


def test_st_pignn_forward_pass():
    """Test ST-PIGNN full fusion model."""
    fusion = STPIGNNFusion()
    x = torch.randn(5, 8)
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]])
    edge_attr = torch.randn(3, 2)
    temporal_x = torch.randn(5, 12, 8)

    embeddings, scores = fusion(x, edge_index, edge_attr, temporal_x)
    assert embeddings.shape == (5, 32)
    assert scores.shape == (5, 1)
    assert torch.all(scores >= 0.0) and torch.all(scores <= 1.0)


def test_all_graph_modules_importable():
    """Verify all graph modules can be imported."""
    assert TrustGraph is not None
    assert KDTreeEnricher is not None
    assert GINEConv is not None
    assert GRUTemporal is not None
    assert STPIGNNFusion is not None
