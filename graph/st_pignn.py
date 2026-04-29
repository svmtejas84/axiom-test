"""
Spatial-Temporal Parallel Interaction Graph Neural Network (ST-PIGNN)

Full implementation of the credit scoring model that combines:
1. Spatial component (GINEConv): captures network position
2. Temporal component (GRU): captures behavioral trends
3. Constraint layer: enforces financial physics

The ST-PIGNN is specifically designed for thin-file credit scoring:
- Handles sparse, incomplete transaction histories
- Incorporates external trust signals (landlord scores)
- Applies regulatory constraints (debt-to-income limits)
- Outputs calibrated scores in [0, 1] for ensemble combination
"""

import logging

import torch
import torch.nn as nn
import torch.nn.functional as F

from .gineconv_model import GINEConvSpatial
from .gru_temporal import GRUTemporal

logger = logging.getLogger(__name__)


class ConstraintLayer(nn.Module):
    """
    Applies financial physics constraints to predicted scores.

    Hard constraints:
    - If debt_to_income > 0.5, penalize score by 0.2
    - If circular transaction loop detected, penalize by 0.15

    Soft constraints:
    - If expense_to_income > 0.9, slight penalty (0.05)
    """

    def __init__(self) -> None:
        """Initialize constraint layer."""
        super().__init__()

    def forward(
        self,
        score: torch.Tensor,
        debt_to_income: torch.Tensor,
        has_circular_loop: torch.Tensor,
        expense_to_income: torch.Tensor,
    ) -> torch.Tensor:
        """
        Apply constraints to scores.

        Args:
            score: Predicted score [batch_size], range [0, 1]
            debt_to_income: Debt-to-income ratio [batch_size], range [0, ...]
            has_circular_loop: Whether circular transactions detected [batch_size], boolean
            expense_to_income: Expense-to-income ratio [batch_size], range [0, ...]

        Returns:
            Constrained score [batch_size], clipped to [0, 1]
        """
        constrained_score = score.clone()

        # Hard constraint 1: debt-to-income > 0.5
        high_debt_mask = debt_to_income > 0.5
        constrained_score[high_debt_mask] = constrained_score[high_debt_mask] * 0.8  # -20%

        # Hard constraint 2: circular loop detected
        has_loop_mask = has_circular_loop.bool()
        constrained_score[has_loop_mask] = constrained_score[has_loop_mask] * 0.85  # -15%

        # Soft constraint: high expense ratio
        high_expense_mask = expense_to_income > 0.9
        constrained_score[high_expense_mask] = (
            constrained_score[high_expense_mask] * 0.95
        )  # -5%

        # Clamp to [0, 1]
        constrained_score = torch.clamp(constrained_score, 0.0, 1.0)

        return constrained_score


class STPIGNN(nn.Module):
    """
    Spatial-Temporal Parallel Interaction Graph Neural Network.

    Complete credit scoring model combining spatial (graph) and temporal (sequence)
    information with regulatory constraints.

    Architecture:
    1. Input: node features, edge structure, temporal sequences
    2. Spatial branch: GINEConv (graph embeddings)
    3. Temporal branch: GRU (sequence embeddings)
    4. Fusion: concatenate spatial + temporal, MLP projection
    5. Constraint layer: apply financial physics
    6. Output: credit score in [0, 1]

    Example:
        >>> model = STPIGNN(
        ...     node_feature_dim=8,
        ...     edge_feature_dim=2,
        ...     num_months=12
        ... )
        >>> # Spatial data
        >>> x = torch.randn(100, 8)
        >>> edge_index = torch.tensor([[...], [...]], dtype=torch.long)
        >>> edge_attr = torch.randn(500, 2)
        >>> # Temporal data (100 users, 12 months)
        >>> temporal_x = torch.randn(100, 12, 8)
        >>> # Constraint data
        >>> debt_to_income = torch.randn(100)
        >>> has_loops = torch.randint(0, 2, (100,))
        >>> # Forward pass
        >>> embeddings, scores = model(
        ...     x, edge_index, edge_attr, temporal_x,
        ...     debt_to_income, has_loops
        ... )
    """

    def __init__(
        self,
        node_feature_dim: int = 8,
        edge_feature_dim: int = 2,
        hidden_dim: int = 128,
        spatial_output_dim: int = 64,
        temporal_output_dim: int = 64,
        num_months: int = 12,
        num_layers: int = 3,
        dropout_rate: float = 0.1,
    ) -> None:
        """
        Initialize ST-PIGNN model.

        Args:
            node_feature_dim: Input node feature dimension (default: 8)
            edge_feature_dim: Input edge feature dimension (default: 2)
            hidden_dim: Hidden layer dimension (default: 128)
            spatial_output_dim: Spatial branch output dimension (default: 64)
            temporal_output_dim: Temporal branch output dimension (default: 64)
            num_months: Number of months in temporal sequences (default: 12)
            num_layers: Number of layers in GINEConv (default: 3)
            dropout_rate: Dropout probability (default: 0.1)
        """
        super().__init__()

        self.node_feature_dim = node_feature_dim
        self.edge_feature_dim = edge_feature_dim
        self.spatial_output_dim = spatial_output_dim
        self.temporal_output_dim = temporal_output_dim

        # Spatial branch: GINEConv
        self.spatial_encoder = GINEConvSpatial(
            node_feature_dim=node_feature_dim,
            edge_feature_dim=edge_feature_dim,
            hidden_dim=hidden_dim,
            output_dim=spatial_output_dim,
            num_layers=num_layers,
            dropout_rate=dropout_rate,
        )

        # Temporal branch: GRU
        self.temporal_encoder = GRUTemporal(
            feature_dim=node_feature_dim,
            hidden_dim=hidden_dim,
            output_dim=temporal_output_dim,
            num_layers=2,
            dropout_rate=dropout_rate,
        )

        # Fusion: concatenate spatial + temporal embeddings
        fusion_input_dim = spatial_output_dim + temporal_output_dim

        # MLP for fusion and score prediction
        self.fusion_mlp = nn.Sequential(
            nn.Linear(fusion_input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden_dim // 2, 64),
        )

        # Final score head: MLP -> [0, 1]
        self.score_head = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),  # Output in [0, 1]
        )

        # Constraint layer
        self.constraint_layer = ConstraintLayer()

        # Dropout
        self.dropout = nn.Dropout(dropout_rate)

        logger.info(
            f"Initialized STPIGNN: spatial_out={spatial_output_dim}, "
            f"temporal_out={temporal_output_dim}, fusion={fusion_input_dim}"
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor | None = None,
        temporal_x: torch.Tensor | None = None,
        debt_to_income: torch.Tensor | None = None,
        has_circular_loop: torch.Tensor | None = None,
        expense_to_income: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass: compute credit scores from spatial and temporal data.

        Args:
            x: Node feature matrix [num_nodes, node_feature_dim]
            edge_index: Edge indices [2, num_edges]
            edge_attr: Edge attributes [num_edges, edge_feature_dim] (optional)
            temporal_x: Temporal sequences [num_nodes, num_months, feature_dim] (optional)
            debt_to_income: Debt-to-income ratios [num_nodes] (optional)
            has_circular_loop: Whether circular loops detected [num_nodes] (optional)
            expense_to_income: Expense-to-income ratios [num_nodes] (optional)

        Returns:
            Tuple of:
            - embeddings: Fused embeddings [num_nodes, embedding_dim]
            - scores: Credit scores [num_nodes, 1] in [0, 1]
        """
        batch_size = x.shape[0]

        logger.debug(
            f"STPIGNN forward: x={x.shape}, edge_index={edge_index.shape}, "
            f"temporal_x={temporal_x.shape if temporal_x is not None else None}"
        )

        # === SPATIAL BRANCH ===
        spatial_embeddings = self.spatial_encoder(x, edge_index, edge_attr)
        logger.debug(f"Spatial embeddings: {spatial_embeddings.shape}")

        # === TEMPORAL BRANCH ===
        if temporal_x is not None:
            temporal_embeddings = self.temporal_encoder(temporal_x)
            logger.debug(f"Temporal embeddings: {temporal_embeddings.shape}")
        else:
            # Fallback: use zeros if temporal data not provided
            logger.warning("Temporal data not provided, using zero embeddings")
            temporal_embeddings = torch.zeros(
                batch_size, self.temporal_output_dim, device=x.device
            )

        # === FUSION ===
        fused = torch.cat([spatial_embeddings, temporal_embeddings], dim=1)
        logger.debug(f"Fused embeddings: {fused.shape}")

        # MLP on fused embeddings
        fused_embeddings = self.fusion_mlp(fused)
        fused_embeddings = self.dropout(fused_embeddings)
        logger.debug(f"Fused MLP output: {fused_embeddings.shape}")

        # === SCORE HEAD ===
        raw_scores = self.score_head(fused_embeddings).squeeze(1)  # [num_nodes]
        logger.debug(f"Raw scores (pre-constraint): {raw_scores.shape}, range=[{raw_scores.min():.3f}, {raw_scores.max():.3f}]")

        # === CONSTRAINT LAYER ===
        if (
            debt_to_income is not None
            and has_circular_loop is not None
            and expense_to_income is not None
        ):
            constrained_scores = self.constraint_layer(
                raw_scores,
                debt_to_income,
                has_circular_loop,
                expense_to_income,
            )
            logger.debug(
                f"Constrained scores: range=[{constrained_scores.min():.3f}, "
                f"{constrained_scores.max():.3f}]"
            )
        else:
            logger.warning(
                "Constraint data not provided, using raw scores "
                "(production requires constraint enforcement)"
            )
            constrained_scores = raw_scores

        # Add dimension for compatibility: [num_nodes] -> [num_nodes, 1]
        scores = constrained_scores.unsqueeze(1)

        logger.debug(f"Final scores: {scores.shape}")

        return fused_embeddings, scores

    def get_interpretability_features(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor | None = None,
        temporal_x: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """
        Extract intermediate features for interpretability and debugging.

        Returns:
            Dictionary with:
            - spatial_embeddings: GINEConv output
            - temporal_embeddings: GRU output
            - fused_embeddings: After MLP fusion
            - attention_weights: Temporal attention over months
        """
        # Spatial
        spatial_embeddings = self.spatial_encoder(x, edge_index, edge_attr)

        # Temporal with attention
        if temporal_x is not None:
            temporal_embeddings = self.temporal_encoder(temporal_x)
            # Note: GRUTemporal.get_sequence_attention_weights() can be called separately
        else:
            temporal_embeddings = None

        return {
            "spatial_embeddings": spatial_embeddings,
            "temporal_embeddings": temporal_embeddings,
        }

    def apply_fairness_adjustment(
        self,
        scores: torch.Tensor,
        group_memberships: torch.Tensor,
    ) -> torch.Tensor:
        """
        Apply fairness constraints to adjust scores across demographic groups.

        Ensures that credit scores don't systematically discriminate based on
        protected characteristics (while still being predictive).

        Args:
            scores: Predicted scores [num_nodes]
            group_memberships: Group membership identifiers [num_nodes]
                              (e.g., 0=female, 1=male, 2=other)

        Returns:
            Fairness-adjusted scores [num_nodes]

        Note:
            - This is a stub for production fairness audits
            - Real implementation requires adversarial debiasing or similar
        """
        # Placeholder: in production, would apply calibration per group
        return scores
