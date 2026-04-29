"""
GINEConv Spatial Graph Neural Network Module

This module implements the spatial component of the ST-PIGNN (Spatial-Temporal 
Parallel Interaction Graph Neural Network) using PyTorch Geometric's GINEConv.

GINEConv (Graph Isomorphism Network with Edge attributes) is superior to simpler
GCN because it:
1. Preserves the Weisfeiler-Lehman expressive power
2. Handles edge attributes (transaction frequency, trust weight)
3. Applies non-linear aggregation (MLP on neighborhood)

For credit scoring, this means:
- Two users with identical in-degree but different relationship quality are
  scored differently (GCN would score them the same)
- Transaction frequency is preserved in embeddings
- The model can distinguish between 1 large transfer and 10 small ones
"""

import logging

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GINEConv, global_mean_pool

logger = logging.getLogger(__name__)


class GINEConvSpatial(nn.Module):
    """
    Spatial graph embedding layer using GINEConv.

    This layer processes graph structure and edge attributes to produce
    node embeddings that capture the user's position in the trust network.

    Architecture:
    - 3 GINEConv layers (expandable)
    - Hidden dimension: 128
    - Output dimension: 64
    - Edge feature dimension: 2 (trust_weight, frequency)

    The output embeddings capture:
    - Transitive trust (high-scoring neighbors)
    - Network density (many vs few connections)
    - Relationship quality (high-trust vs low-trust edges)

    Example:
        >>> spatial = GINEConvSpatial(
        ...     node_feature_dim=8,
        ...     edge_feature_dim=2
        ... )
        >>> x = torch.randn(100, 8)  # 100 nodes, 8 features each
        >>> edge_index = torch.tensor([[...], [...]], dtype=torch.long)
        >>> edge_attr = torch.randn(500, 2)  # 500 edges, 2 attrs each
        >>> embeddings = spatial(x, edge_index, edge_attr)
        >>> print(embeddings.shape)  # [100, 64]
    """

    def __init__(
        self,
        node_feature_dim: int = 8,
        edge_feature_dim: int = 2,
        hidden_dim: int = 128,
        output_dim: int = 64,
        num_layers: int = 3,
        dropout_rate: float = 0.1,
    ) -> None:
        """
        Initialize GINEConv spatial layer.

        Args:
            node_feature_dim: Input node feature dimension (default: 8)
            edge_feature_dim: Input edge feature dimension (default: 2)
            hidden_dim: Hidden layer dimension (default: 128)
            output_dim: Output embedding dimension (default: 64)
            num_layers: Number of GINEConv layers (default: 3)
            dropout_rate: Dropout probability for regularization (default: 0.1)
        """
        super().__init__()

        self.node_feature_dim = node_feature_dim
        self.edge_feature_dim = edge_feature_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.num_layers = num_layers

        # Input projection: embed input features to hidden dimension
        self.input_projection = nn.Linear(node_feature_dim, hidden_dim)

        # GINEConv layers with edge attributes
        self.gine_layers = nn.ModuleList()
        for i in range(num_layers):
            in_dim = hidden_dim if i > 0 else hidden_dim
            out_dim = hidden_dim if i < num_layers - 1 else output_dim

            # MLP for GINEConv neighborhood aggregation
            mlp = nn.Sequential(
                nn.Linear(in_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout_rate),
                nn.Linear(hidden_dim, out_dim),
            )

            # Edge network to process edge attributes
            edge_nn = nn.Sequential(
                nn.Linear(edge_feature_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, out_dim),
            )

            gine_layer = GINEConv(mlp, edge_nn=edge_nn)
            self.gine_layers.append(gine_layer)

        # Output projection to final embedding dimension
        self.output_projection = nn.Linear(output_dim, output_dim)

        # Batch normalization for stable training
        self.batch_norms = nn.ModuleList(
            [nn.BatchNorm1d(output_dim) for _ in range(num_layers)]
        )

        self.dropout = nn.Dropout(dropout_rate)
        self.relu = nn.ReLU()

        logger.info(
            f"Initialized GINEConvSpatial: "
            f"input_dim={node_feature_dim}, hidden={hidden_dim}, "
            f"output={output_dim}, layers={num_layers}"
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """
        Forward pass: compute spatial embeddings from graph structure.

        Args:
            x: Node feature matrix, shape [num_nodes, node_feature_dim]
            edge_index: Edge indices, shape [2, num_edges]
                       Format: [[src_nodes], [dst_nodes]]
            edge_attr: Edge attributes, shape [num_edges, edge_feature_dim]
                      If None, GINEConv uses ones

        Returns:
            Node embeddings, shape [num_nodes, output_dim]

        Note:
            - Implements skip connections (residual) between layers
            - Uses ReLU activations between layers
            - Applies dropout for regularization
        """
        logger.debug(
            f"GINEConvSpatial forward: x={x.shape}, "
            f"edge_index={edge_index.shape}, edge_attr={edge_attr.shape if edge_attr is not None else None}"
        )

        # Project input to hidden dimension
        x = self.input_projection(x)
        x = self.relu(x)

        # Pass through GINEConv layers
        for i, gine_layer in enumerate(self.gine_layers):
            # GINEConv forward pass
            x_prev = x
            x = gine_layer(x, edge_index, edge_attr)

            # Batch normalization
            x = self.batch_norms[i](x)

            # Activation and dropout
            x = self.relu(x)
            x = self.dropout(x)

            # Skip connection (residual) if dimensions match
            if x_prev.shape == x.shape:
                x = x + x_prev

        # Final output projection
        x = self.output_projection(x)

        logger.debug(f"GINEConvSpatial output shape: {x.shape}")

        return x

    def get_intermediate_representations(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor | None = None,
    ) -> list[torch.Tensor]:
        """
        Get intermediate representations from each layer (for debugging/analysis).

        Args:
            x: Node features
            edge_index: Edge indices
            edge_attr: Edge attributes

        Returns:
            List of embeddings from each layer
        """
        representations = []

        x = self.input_projection(x)
        x = self.relu(x)
        representations.append(x)

        for i, gine_layer in enumerate(self.gine_layers):
            x_prev = x
            x = gine_layer(x, edge_index, edge_attr)
            x = self.batch_norms[i](x)
            x = self.relu(x)
            x = self.dropout(x)

            if x_prev.shape == x.shape:
                x = x + x_prev

            representations.append(x)

        x = self.output_projection(x)
        representations.append(x)

        return representations


class EdgeAttributeProcessor(nn.Module):
    """
    Processes edge attributes (transaction metadata) for GINEConv.

    Converts raw transaction data (frequency, trust weight) into a format
    suitable for neural processing.
    """

    def __init__(self, edge_feature_dim: int = 2) -> None:
        """
        Initialize edge attribute processor.

        Args:
            edge_feature_dim: Output dimension for edge embeddings
        """
        super().__init__()
        self.edge_feature_dim = edge_feature_dim

    def forward(self, frequency: torch.Tensor, trust_weight: torch.Tensor) -> torch.Tensor:
        """
        Process edge attributes.

        Args:
            frequency: Encoded transaction frequency (0-3)
            trust_weight: Trust coefficient (0-1)

        Returns:
            Processed edge attributes, shape [num_edges, edge_feature_dim]
        """
        # Stack frequency and trust weight
        edge_attr = torch.stack([frequency, trust_weight], dim=1)
        return edge_attr
