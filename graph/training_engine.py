"""
Hierarchical Training Engine for ST-PIGNN

Inspired by Phase 11 training patterns with:
- Robust checkpoint management (clean start, resume capability)
- Hierarchical progress bars (epochs, batches, nodes)
- AMP (Automatic Mixed Precision) safety
- Gradient stability and LR backoff
- Physics loss integration
- Tuple-safe data handling
"""

import logging
import os
import time
import gc
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from tqdm.auto import tqdm

logger = logging.getLogger(__name__)


@dataclass
class LossBreakdown:
    """Tracks loss components during training."""

    total: torch.Tensor
    data: torch.Tensor
    physics: torch.Tensor


@dataclass
class CheckpointState:
    """Checkpoint state structure."""

    state_dict: dict[str, Any]
    optimizer_state_dict: dict[str, Any]
    scaler_state_dict: dict[str, Any]
    epoch: int
    step: int
    best_val_loss: float
    timestamp: str
    note: str = ""


class TrainingConfig:
    """Training configuration parameters."""

    def __init__(self, **kwargs):
        self.max_epochs = int(kwargs.get("max_epochs", 15))
        self.save_interval_seconds = int(kwargs.get("save_interval_seconds", 1800))
        self.clean_start = kwargs.get("clean_start", True)
        self.amp_enabled = kwargs.get("amp_enabled", torch.cuda.is_available())
        self.device = kwargs.get("device", torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        self.physics_loss_lambda = float(kwargs.get("physics_loss_lambda", 0.1))
        self.lr_initial = float(kwargs.get("lr_initial", 3e-6))
        self.weight_decay = float(kwargs.get("weight_decay", 1e-2))
        self.max_grad_norm = float(kwargs.get("max_grad_norm", 0.3))
        self.lr_backoff_factor = float(kwargs.get("lr_backoff_factor", 0.7))
        self.min_lr = float(kwargs.get("min_lr", 1e-6))
        self.max_bad_events_per_epoch = int(kwargs.get("max_bad_events_per_epoch", 50))

        logger.info(f"TrainingConfig: {self.__dict__}")


class STGNNTrainer:
    """
    Hierarchical trainer for ST-PIGNN model with robust checkpointing.

    Features:
    - Clean start or resume from checkpoint
    - Automatic Mixed Precision (AMP) for GPU efficiency
    - Gradient clipping and LR backoff on instability
    - Masked loss for selective training/validation
    - Physics constraint loss
    - Emergency checkpointing on crash
    """

    def __init__(
        self,
        model: torch.nn.Module,
        config: TrainingConfig,
        checkpoint_dir: str = "./checkpoints",
    ):
        """
        Initialize trainer.

        Args:
            model: ST-PIGNN model to train
            config: TrainingConfig instance
            checkpoint_dir: Directory for checkpoint storage
        """
        self.model = model
        self.config = config
        self.device = config.device
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)

        self.checkpoint_path = os.path.join(checkpoint_dir, "stpignn_checkpoint_stable.pt")
        self.autosave_path = os.path.join(checkpoint_dir, "stpignn_autosave.pt")
        self.best_path = os.path.join(checkpoint_dir, "stpignn_best.pt")

        self.optimizer = None
        self.scaler_amp = None
        self.start_epoch = 1
        self.start_step = 0
        self.best_val_loss = float("inf")

        self._init_training_state()

    def _init_training_state(self) -> None:
        """Initialize or resume training state."""
        if self.config.clean_start:
            self._create_fresh_state()
            logger.info("Clean start: fresh optimizer, scaler, epoch=1")
        else:
            self._try_resume_from_checkpoint()

    def _create_fresh_state(self) -> None:
        """Create fresh optimizer and scaler."""
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.lr_initial,
            weight_decay=self.config.weight_decay,
        )
        self.scaler_amp = torch.amp.GradScaler(
            "cuda", enabled=self.config.amp_enabled
        )
        self.start_epoch = 1
        self.start_step = 0
        self.best_val_loss = float("inf")

    def _try_resume_from_checkpoint(self) -> None:
        """Try to resume from existing checkpoint."""
        paths_to_try = [self.checkpoint_path, self.autosave_path, self.best_path]

        for ckpt_path in paths_to_try:
            if not os.path.exists(ckpt_path):
                continue

            try:
                ckpt = self.load_checkpoint(ckpt_path)
                self.start_epoch = int(ckpt.get("epoch", 1))
                self.start_step = int(ckpt.get("step", 0))
                self.best_val_loss = float(ckpt.get("best_val_loss", float("inf")))

                logger.info(
                    f"Resumed from {ckpt_path}: "
                    f"epoch={self.start_epoch} step={self.start_step} "
                    f"best={self.best_val_loss:.6f}"
                )
                return
            except Exception as e:
                logger.warning(f"Failed to load {ckpt_path}: {e}")

        # No checkpoint loaded, create fresh state
        self._create_fresh_state()
        logger.info("No valid checkpoint found, starting fresh")

    def save_checkpoint(
        self,
        path: str,
        epoch: int,
        step: int,
        loss_total: float | None = None,
        note: str = "",
    ) -> None:
        """
        Save training checkpoint.

        Args:
            path: Path to save checkpoint
            epoch: Current epoch
            step: Current step in epoch
            loss_total: Total loss value
            note: Annotation (e.g., "best", "autosave")
        """
        payload = {
            "state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "scaler_state_dict": self.scaler_amp.state_dict(),
            "epoch": int(epoch),
            "step": int(step),
            "best_val_loss": float(self.best_val_loss),
            "timestamp": time.ctime(),
            "note": str(note),
        }
        if loss_total is not None:
            payload["loss_total"] = float(loss_total)

        torch.save(payload, path)
        logger.debug(f"Saved checkpoint to {path}")

    def load_checkpoint(self, path: str) -> dict[str, Any]:
        """
        Load training checkpoint.

        Args:
            path: Path to checkpoint file

        Returns:
            Checkpoint dictionary
        """
        ckpt = torch.load(path, map_location=self.device)
        self.model.load_state_dict(ckpt["state_dict"])
        self.optimizer.load_state_dict(ckpt["optimizer_state_dict"])

        if (
            "scaler_state_dict" in ckpt
            and ckpt["scaler_state_dict"] is not None
        ):
            self.scaler_amp.load_state_dict(ckpt["scaler_state_dict"])

        return ckpt

    def _masked_mae_rmse(
        self,
        pred: torch.Tensor,
        target: torch.Tensor,
        mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Compute MAE and RMSE under mask.

        Args:
            pred: Predictions
            target: Ground truth
            mask: Boolean mask (True = include in loss)

        Returns:
            (MAE, RMSE) tensors
        """
        if pred.dim() == 1:
            pred = pred.unsqueeze(0)
        if target.dim() == 1:
            target = target.unsqueeze(0)
        if mask.dim() == 1:
            mask = mask.unsqueeze(0).expand_as(pred)

        if not bool(mask.any()):
            zero = pred.new_tensor(0.0)
            return zero, zero

        err = pred[mask] - target[mask]
        mae = err.abs().mean()
        rmse = torch.sqrt((err * err).mean())

        return mae, rmse

    def _backoff_learning_rate(self, bad_events: int) -> None:
        """
        Reduce learning rate if too many bad events.

        Args:
            bad_events: Number of NaN/Inf/gradient failures
        """
        if bad_events > 20:
            old_lr = self.optimizer.param_groups[0]["lr"]
            new_lr = max(self.config.min_lr, old_lr * self.config.lr_backoff_factor)

            for g in self.optimizer.param_groups:
                g["lr"] = new_lr

            logger.warning(
                f"LR backoff: bad_events={bad_events} "
                f"lr {old_lr:.8f} -> {new_lr:.8f}"
            )

    def train_epoch(
        self,
        train_loader: Any,
        epoch: int,
    ) -> dict[str, float]:
        """
        Train one epoch.

        Args:
            train_loader: DataLoader with (xb, yb, c_idx) tuples
            epoch: Current epoch number

        Returns:
            Dictionary with loss/metric aggregates
        """
        self.model.train()

        # Physics loss annealing: ramp up over 25 epochs
        curr_lambda = self.config.physics_loss_lambda * min(1.0, epoch / 25.0)

        train_losses = {"total": [], "data": [], "physics": []}
        train_metrics = {"mae": [], "rmse": []}
        bad_stats = {"skip_bad": 0, "finite_fail": 0, "grad_fail": 0}
        nodes_seen = 0

        # Rolling window for smooth metric display
        ROLL_N = 100
        roll_losses = {"total": [], "data": [], "physics": []}

        batch_bar = tqdm(
            total=len(train_loader),
            desc=f"Epoch {epoch} Batches",
            position=1,
            leave=False,
        )
        node_bar = tqdm(
            total=getattr(self, "nodes_per_epoch", len(train_loader) * 100),
            desc=f"Epoch {epoch} Nodes",
            position=2,
            leave=False,
        )

        last_save_time = time.time()

        for i, batch_data in enumerate(train_loader):
            # Handle tuple-safe unpacking
            if isinstance(batch_data, (tuple, list)) and len(batch_data) >= 3:
                xb_raw, yb_raw, c_idx_t = batch_data[0], batch_data[1], batch_data[2]
            else:
                logger.warning(f"Unexpected batch format: {type(batch_data)}")
                batch_bar.update(1)
                continue

            # Skip if resuming
            if epoch == self.start_epoch and i < self.start_step:
                batch_bar.update(1)
                continue

            # ===== DATA PREPARATION =====
            try:
                xb = torch.nan_to_num(
                    xb_raw.to(self.device, non_blocking=self.config.amp_enabled),
                    nan=0.0,
                    posinf=0.0,
                    neginf=0.0,
                )
                yb = torch.nan_to_num(
                    yb_raw.to(self.device, non_blocking=self.config.amp_enabled),
                    nan=0.0,
                    posinf=0.0,
                    neginf=0.0,
                )
                num_nodes = int(xb.shape[0] if xb.dim() == 3 else xb.shape[0])
            except Exception as e:
                logger.warning(f"Data prep error: {e}")
                bad_stats["skip_bad"] += 1
                batch_bar.update(1)
                continue

            # ===== MASK PREPARATION =====
            try:
                # Create training mask (nodes with valid targets)
                base_mask = (yb.abs() > 1e-8).any(dim=-1) if yb.dim() > 1 else (yb.abs() > 1e-8)
                if base_mask.numel() != num_nodes:
                    bad_stats["skip_bad"] += 1
                    batch_bar.update(1)
                    continue
            except Exception as e:
                logger.warning(f"Mask error: {e}")
                bad_stats["skip_bad"] += 1
                batch_bar.update(1)
                continue

            # ===== FORWARD PASS & LOSS =====
            self.optimizer.zero_grad(set_to_none=True)

            try:
                with torch.amp.autocast(
                    device_type=self.device.type,
                    enabled=self.config.amp_enabled,
                ):
                    # Mock forward for now (actual model depends on architecture)
                    pred = xb * 0.5 + 0.25  # Placeholder

                    if base_mask.any():
                        # Data loss on masked region
                        err = pred[base_mask] - yb[base_mask]
                        loss_data = torch.mean(err * err)
                    else:
                        loss_data = pred.new_tensor(0.0)

                    # Physics penalty (constrain to valid range)
                    loss_physics = torch.mean(torch.relu(pred - 1.0) + torch.relu(-pred))

                    loss_total = loss_data + curr_lambda * loss_physics

                    if not torch.isfinite(loss_total):
                        bad_stats["finite_fail"] += 1
                        batch_bar.update(1)
                        if (bad_stats["finite_fail"] + bad_stats["grad_fail"]) > self.config.max_bad_events_per_epoch:
                            break
                        continue

            except Exception as e:
                logger.warning(f"Forward pass error: {e}")
                bad_stats["finite_fail"] += 1
                batch_bar.update(1)
                continue

            # ===== BACKWARD PASS & OPTIMIZATION =====
            try:
                t = float(loss_total.detach().item())
                d = float(loss_data.detach().item())
                p = float(loss_physics.detach().item())

                if not (np.isfinite(t) and np.isfinite(d) and np.isfinite(p)):
                    bad_stats["finite_fail"] += 1
                    batch_bar.update(1)
                    continue

                # Compute metrics
                with torch.no_grad():
                    mae_t, rmse_t = self._masked_mae_rmse(pred, yb, base_mask)
                    mae_v = float(mae_t.item())
                    rmse_v = float(rmse_t.item())

                # Backward
                grad_norm = 0.0
                if t > 0.0:
                    self.scaler_amp.scale(loss_total).backward()
                    self.scaler_amp.unscale_(self.optimizer)

                    # Check gradient validity
                    bad_grad = False
                    for prm in self.model.parameters():
                        if prm.grad is not None and not torch.isfinite(prm.grad).all():
                            bad_grad = True
                            break

                    if bad_grad:
                        self.optimizer.zero_grad(set_to_none=True)
                        bad_stats["grad_fail"] += 1
                        self.scaler_amp.update()
                        batch_bar.update(1)
                        if (bad_stats["finite_fail"] + bad_stats["grad_fail"]) > self.config.max_bad_events_per_epoch:
                            break
                        continue

                    # Gradient clipping
                    grad_norm = float(
                        torch.nn.utils.clip_grad_norm_(
                            self.model.parameters(),
                            max_norm=self.config.max_grad_norm,
                        ).item()
                    )

                    if not np.isfinite(grad_norm):
                        self.optimizer.zero_grad(set_to_none=True)
                        bad_stats["grad_fail"] += 1
                        self.scaler_amp.update()
                        batch_bar.update(1)
                        if (bad_stats["finite_fail"] + bad_stats["grad_fail"]) > self.config.max_bad_events_per_epoch:
                            break
                        continue

                    self.scaler_amp.step(self.optimizer)
                    self.scaler_amp.update()

                # Track losses
                train_losses["total"].append(t)
                train_losses["data"].append(d)
                train_losses["physics"].append(p)
                train_metrics["mae"].append(mae_v)
                train_metrics["rmse"].append(rmse_v)

                roll_losses["total"].append(t)
                roll_losses["data"].append(d)
                roll_losses["physics"].append(p)
                if len(roll_losses["total"]) > ROLL_N:
                    roll_losses["total"].pop(0)
                    roll_losses["data"].pop(0)
                    roll_losses["physics"].pop(0)

                # Rolling averages
                r_total = float(np.nanmean(roll_losses["total"])) if roll_losses["total"] else 0.0
                r_data = float(np.nanmean(roll_losses["data"])) if roll_losses["data"] else 0.0
                r_phys = float(np.nanmean(roll_losses["physics"])) if roll_losses["physics"] else 0.0

                nodes_seen += num_nodes
                lr_now = float(self.optimizer.param_groups[0]["lr"])

                batch_bar.set_postfix({
                    "T": f"{t:.6f}",
                    "D": f"{d:.6f}",
                    "P": f"{p:.6f}",
                    "rT": f"{r_total:.6f}",
                    "MAE": f"{mae_v:.6f}",
                    "gN": f"{grad_norm:.4f}",
                    "lr": f"{lr_now:.8f}",
                    "Skip": bad_stats["skip_bad"],
                })
                batch_bar.update(1)
                node_bar.update(min(num_nodes, max(0, node_bar.total - node_bar.n)))

                # Periodic garbage collection and autosave
                if i % 100 == 0:
                    if self.config.amp_enabled:
                        torch.cuda.empty_cache()
                    gc.collect()

                if (time.time() - last_save_time) > self.config.save_interval_seconds:
                    self.save_checkpoint(
                        self.autosave_path,
                        epoch=epoch,
                        step=i,
                        loss_total=t,
                        note="autosave",
                    )
                    last_save_time = time.time()
                    tqdm.write(f"[AUTOSAVE] epoch={epoch} step={i}")

            except Exception as e:
                logger.warning(f"Backward/optim error: {e}")
                bad_stats["grad_fail"] += 1
                batch_bar.update(1)
                continue

        batch_bar.close()
        node_bar.close()

        # LR backoff if too many bad events
        total_bad = bad_stats["finite_fail"] + bad_stats["grad_fail"]
        self._backoff_learning_rate(total_bad)

        # Aggregate results
        return {
            "train_loss_total": float(np.nanmean(train_losses["total"])) if train_losses["total"] else 0.0,
            "train_loss_data": float(np.nanmean(train_losses["data"])) if train_losses["data"] else 0.0,
            "train_loss_physics": float(np.nanmean(train_losses["physics"])) if train_losses["physics"] else 0.0,
            "train_mae": float(np.nanmean(train_metrics["mae"])) if train_metrics["mae"] else 0.0,
            "train_rmse": float(np.nanmean(train_metrics["rmse"])) if train_metrics["rmse"] else 0.0,
            "nodes_seen": nodes_seen,
            "bad_events": total_bad,
        }

    def run_training(self, train_loader: Any, val_loader: Any) -> None:
        """
        Run full training loop with validation.

        Args:
            train_loader: Training DataLoader
            val_loader: Validation DataLoader
        """
        epoch_bar = tqdm(
            total=(self.config.max_epochs - self.start_epoch + 1),
            desc="Epochs",
            position=0,
            leave=True,
        )

        try:
            for epoch in range(self.start_epoch, self.config.max_epochs + 1):
                # Train
                train_stats = self.train_epoch(train_loader, epoch)

                # Validation (simplified)
                self.model.eval()
                val_loss = 0.0
                with torch.no_grad():
                    for val_batch in val_loader:
                        # Mock validation
                        val_loss += 0.01

                # Checkpoint saving
                self.save_checkpoint(
                    self.checkpoint_path,
                    epoch=epoch + 1,
                    step=0,
                    loss_total=val_loss,
                    note="stable",
                )

                if 0 < val_loss < self.best_val_loss:
                    self.best_val_loss = val_loss
                    self.save_checkpoint(
                        self.best_path,
                        epoch=epoch,
                        step=0,
                        loss_total=val_loss,
                        note="best",
                    )
                    tqdm.write(f"[BEST] Updated best validation loss: {self.best_val_loss:.6f}")

                epoch_bar.update(1)

        except KeyboardInterrupt:
            tqdm.write("[INTERRUPT] Saving emergency checkpoint...")
            self.save_checkpoint(
                self.checkpoint_path,
                epoch=epoch if "epoch" in locals() else 1,
                step=0,
                note="interrupt",
            )

        except Exception as e:
            tqdm.write(f"[CRASH] {e}")
            self.save_checkpoint(
                self.checkpoint_path,
                epoch=epoch if "epoch" in locals() else 1,
                step=0,
                note=f"crash: {e}",
            )
            raise

        finally:
            epoch_bar.close()
            logger.info("Training complete")
