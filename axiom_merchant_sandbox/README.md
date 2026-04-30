# Axiom Merchant Sandbox

A dedicated test environment for **Universal Merchant Resolution** and **Frequency-Based Trust Mapping**. This sandbox is used to resolve messy transaction strings from raw bank statements into verified GSTINs and physical addresses to power the Axiom Credit Platform's Neighborhood Trust Loop ($S_N$ and $S_T$ scores).

## Core Modules

### 1. `resolve_merchants.py`
The primary resolution engine. It implements a **Live Free Multi-Stage Resolution** pipeline:
- **Stage 1 (DDGS)**: Uses DuckDuckGo search snippets to find pincodes and addresses.
- **Stage 2 (IndiaGST)**: Fallback scraping of `indiagst.in` for entities that fail Stage 1.
- **Frequency Analysis**: Identifies the Top 50 counterparties appearing $\ge 3$ times.
- **Categorization**: Segregates local merchants from High-Trust P2P nodes (Landlords, vendors).
- **Spatial Indexing**: Uses `KDTreeEnricher` to map resolved merchants into the spatial trust graph.

### 2. `run_axiom_stateless.py`
The **End-to-End Stateless Scoring Pipeline**. This script bridges the sandbox with the core Axiom production modules:
- **Zero-Footprint**: Processes everything in volatile memory; no database writes.
- **Ingestion**: Feeds utility signals (ACT Fibernet, BESCOM) into the `UtilityTracker`.
- **GNN Execution**: Pushes graph tensors to the **RTX 4050 (CUDA)** for ST-PIGNN scoring.
- **Ensemble Fusion**: Combines spatial, temporal, and behavior signals into a final **300-900 Axiom Score**.
- **Memory Purge**: Explicitly clears VRAM and RAM using `gc.collect()` and `torch.cuda.empty_cache()` post-execution.

## How to Run

1. **Install Dependencies**:
   ```bash
   pip install ddgs rapidfuzz tqdm beautifulsoup4 torch torch-geometric
   ```

2. **Run the Full Pipeline**:
   ```bash
   python run_axiom_stateless.py
   ```

## Key Metrics Generated
- **Neighborhood Density**: Calculated as `Merchants/km²` within a 2.0km radius.
- **Transitive Trust (S_T)**: Derived from the GINEConv graph layers.
- **Utility Discipline (S_B)**: Derived from the rhythmic analysis of monthly bills.
- **Axiom Score**: The final credit risk assessment.

---
**Status**: End-to-End Integration Verified.
**Target Hardware**: ASUS ROG Strix G16 (RTX 4050).
