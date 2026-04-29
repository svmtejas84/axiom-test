"""
GRU Temporal Sequence Modeling Module

This module implements the temporal component of the ST-PIGNN using GRU layers.

Why GRU over LSTM for credit scoring?
1. Fewer parameters → less prone to overfitting on sparse thin-file data
2. Captures behavioral patterns at monthly granularity
3. Faster training and inference
4. Good performance on short sequences (12-24 months of history)

The GRU processes monthly snapshots of user behavior to capture:
- Seasonal patterns (higher spending in months with weddings, festivals)
- Trend changes (gradually increasing or decreasing income/expenses)
- Anomalies (sudden behavior shifts indicating fraud or life events)
"""

import logging

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class GRUTemporal(nn.Module):
    """
    Temporal sequence modeling using GRU layers.

    Processes a sequence of monthly behavioral snapshots to capture temporal
    dynamics of user financial behavior.

    Architecture:
    - 2 GRU layers (stacked)
    - Hidden dimension: 64
    - Output dimension: 64
    - Sequence length: 12 months (typical)

    Input: [num_nodes, num_months, feature_dim]
    Output: [num_nodes, output_dim]

    Example:
        >>> temporal = GRUTemporal(
        ...     feature_dim=8,
        ...     hidden_dim=64,
        ...     num_layers=2
        ... )
        >>> # 100 users, 12 months of history, 8 features per month
        >>> x = torch.randn(100, 12, 8)
        >>> embeddings = temporal(x)
        >>> print(embeddings.shape)  # [100, 64]
    """

    def __init__(
        self,
        feature_dim: int = 8,
        hidden_dim: int = 64,
        output_dim: int = 64,
        num_layers: int = 2,
        dropout_rate: float = 0.1,
        bidirectional: bool = False,
    ) -> None:
        """
        Initialize GRU temporal layer.

        Args:
            feature_dim: Dimension of input features per timestep
            hidden_dim: Hidden state dimension of GRU
            output_dim: Output embedding dimension
            num_layers: Number of stacked GRU layers (default: 2)
            dropout_rate: Dropout probability between GRU layers
            bidirectional: Whether to use bidirectional GRU (default: False)
                          Bidirectional requires future information,
                          not applicable for real-time credit scoring
        """
        super().__init__()

        self.feature_dim = feature_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional

        # Input projection to hidden dimension
        self.input_projection = nn.Linear(feature_dim, hidden_dim)

        # GRU layers
        self.gru = nn.GRU(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            dropout=dropout_rate if num_layers > 1 else 0.0,
            bidirectional=bidirectional,
            batch_first=True,
        )

        # Calculate GRU output dimension
        gru_output_dim = hidden_dim * (2 if bidirectional else 1)

        # Output projection to final embedding dimension
        self.output_projection = nn.Linear(gru_output_dim, output_dim)

        # Dropout for regularization
        self.dropout = nn.Dropout(dropout_rate)

        logger.info(
            f"Initialized GRUTemporal: feature_dim={feature_dim}, "
            f"hidden={hidden_dim}, output={output_dim}, layers={num_layers}, "
            f"bidirectional={bidirectional}"
        )

    def forward(
        self,
        x: torch.Tensor,
        lengths: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """
        Forward pass: compute temporal embeddings from sequence.

        Args:
            x: Input sequence, shape [batch_size, seq_length, feature_dim]
               Typically: [num_nodes, num_months, behavioral_features]
            lengths: Optional sequence lengths for packed sequences.
                    Shape: [batch_size]
                    If None, all sequences assumed to have full length

        Returns:
            Temporal embeddings, shape [batch_size, output_dim]

        Note:
            - Uses last hidden state as sequence representation
            - Ignores padding for sequences with variable lengths
        """
        logger.debug(
            f"GRUTemporal forward: x={x.shape}, lengths={lengths.shape if lengths is not None else None}"
        )

        batch_size, seq_length, _ = x.shape

        # Project input features to hidden dimension
        x = self.input_projection(x)  # [batch_size, seq_length, hidden_dim]
        x = F.relu(x)
        x = self.dropout(x)

        # Handle variable-length sequences with packing
        if lengths is not None:
            x = nn.utils.rnn.pack_padded_sequence(
                x, lengths.cpu(), batch_first=True, enforce_sorted=False
            )

        # Pass through GRU
        # output: [batch_size, seq_length, hidden_dim * num_directions]
        # h_n: [num_layers * num_directions, batch_size, hidden_dim]
        output, h_n = self.gru(x)

        # Unpack if we packed
        if lengths is not None:
            output, _ = nn.utils.rnn.pad_packed_sequence(output, batch_first=True)

        # Use last hidden state from final GRU layer
        if self.bidirectional:
            # Concatenate forward and backward final states
            h_last = torch.cat([h_n[-2], h_n[-1]], dim=1)  # [batch_size, 2*hidden_dim]
        else:
            h_last = h_n[-1]  # [batch_size, hidden_dim]

        # Project to output dimension
        embeddings = self.output_projection(h_last)  # [batch_size, output_dim]
        embeddings = F.relu(embeddings)
        embeddings = self.dropout(embeddings)

        logger.debug(f"GRUTemporal output shape: {embeddings.shape}")

        return embeddings

    def get_sequence_attention_weights(
        self,
        x: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute attention weights over the sequence (which months are important).

        Uses the GRU hidden states to infer which timesteps are most important
        for the final prediction.

        Args:
            x: Input sequence, shape [batch_size, seq_length, feature_dim]

        Returns:
            Attention weights, shape [batch_size, seq_length]
            (higher weight = more important month)
        """
        batch_size, seq_length, _ = x.shape

        # Project input
        x_proj = self.input_projection(x)
        x_proj = F.relu(x_proj)

        # Pass through GRU (get all hidden states, not just last)
        output, _ = self.gru(x_proj)  # [batch_size, seq_length, hidden_dim]

        # Simple attention: compute similarity of each hidden state to final hidden state
        final_hidden = output[:, -1, :].unsqueeze(2)  # [batch_size, hidden_dim, 1]

        # Attention scores
        scores = torch.bmm(output, final_hidden).squeeze(2)  # [batch_size, seq_length]

        # Softmax to get weights
        weights = torch.softmax(scores, dim=1)

        return weights


class TemporalAnomalyDetector(nn.Module):
    """
    Detects anomalies in temporal behavior sequences.

    Uses autoencoder approach: if reconstruction error is high,
    the month contains anomalous behavior.
    """

    def __init__(self, feature_dim: int = 8, hidden_dim: int = 32) -> None:
        """Initialize temporal anomaly detector."""
        super().__init__()

        # Encoder: compress sequence to bottleneck
        self.encoder = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
        )

        # Decoder: reconstruct sequence from bottleneck
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, feature_dim),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass: encode and reconstruct sequence.

        Args:
            x: Input sequence, shape [batch_size, seq_length, feature_dim]

        Returns:
            Tuple of (reconstruction, reconstruction_error)
        """
        batch_size, seq_length, feature_dim = x.shape

        # Flatten sequence: [batch_size * seq_length, feature_dim]
        x_flat = x.reshape(-1, feature_dim)

        # Encode and decode
        encoded = self.encoder(x_flat)
        decoded = self.decoder(encoded)

        # Reshape back
        reconstruction = decoded.reshape(batch_size, seq_length, feature_dim)

        # Compute reconstruction error
        error = torch.mean((x - reconstruction) ** 2, dim=2)  # [batch_size, seq_length]

        return reconstruction, error
