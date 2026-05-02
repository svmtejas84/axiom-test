# Axiom Credit Scoring - Behavioral Test Data

This folder contains diverse CSV statements and behavioral profiles designed to test the **Equilibrium Engine's** non-linear scoring logic.

## 1. User Behavioral CSVs
Use these files in the "Document Upload" (Option 3) flow to see different Axiom Scores.

*   `high_trust_neighborhood.csv`: Salaried user with clean spending (Pharmacies, Groceries) and high neighborhood density. (Target: 800-850)
*   `medium_trust_neighborhood.csv`: Variable income user with diverse local spending but no utility anchor. (Target: 680-720)
*   `low_trust_neighborhood.csv`: High-risk profile with 30%+ failed transactions and gambling/wine store entries. (Target: 300-450)
*   `test_data1.csv`: Standard real-world statement for baseline verification.

## 2. Graph Reference Nodes (`reputation_nodes.py`)
This file defines 9 distinct "Reference Nodes" used by the GNN to calculate **Transitive Trust ($S_T$)**.

### Categories:
1.  **Students**: Verified edu-email domains vs. unverified high-risk behavior.
2.  **Parents (Trust Inheritance)**: Nodes with high balance and property taxes vs. risky ATM-heavy nodes.
3.  **Landlords (Stability Anchors)**: Institutional registered entities vs. high-risk unverified VPAs.

## 3. How to Test
1. Run `python main_execution.py`.
2. Choose **Option 3** for Document Upload.
3. Provide the path to one of the CSVs (e.g., `examples/high_trust_neighborhood.csv`).
4. (Optional) Provide a **Parent VPA** or **Landlord VPA** when prompted to see how the graph "contagion" affects the score.
