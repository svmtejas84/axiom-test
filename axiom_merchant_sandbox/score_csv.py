"""
Axiom Score CSV Runner (High-Fidelity Map Mode)
Orchestrates Axiom modules and displays a Verified Merchant Map using Seaborn/UTM.
"""

import asyncio
import logging
import os
import sys
import hashlib
import re
from datetime import datetime
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import utm

# Ensure the current directory is in the path
sys.path.append(os.getcwd())

from ingestion.statement_ingest import StatementIngestor
from ingestion.upi_parser import UPIParser
from ingestion.rent_verifier import RentVerifier
from graph.trust_graph import TrustGraph
from graph.kdtree_enricher import KDTreeEnricher, Location
from scoring.baseline_score import BaselineScorer, BaselineFeatures
from scoring.trust_transitive import TransitiveTrustScorer
from scoring.fraud_detector import FraudDetector
from scoring.ensemble import AxiomEnsemble
from scoring.shap_explainer import SHAPExplainer

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("AxiomRunner")

# Verified Merchant Registry (Simulated local database)
MERCHANT_REGISTRY = {
    "bangalore metro rail": {
        "gstin": "29AAACB4881D1ZQ",
        "address": "BMTC Complex, Shanthinagar, Bengaluru, 560027",
        "lat": 12.9592, "lon": 77.5917,
        "category": "transport"
    },
    "uber india systems pr": {
        "gstin": "06AABCU6223H1ZI",
        "address": "One Horizon Centre, Sector 43, Gurugram, 122002",
        "lat": 28.4595, "lon": 77.0266,
        "category": "transport"
    },
    "airtel": {
        "gstin": "29AABCB2640L1ZU",
        "address": "Bharti Airtel Ltd, Mehrauli Road, Gurgaon",
        "lat": 28.4595, "lon": 77.0266,
        "category": "utility"
    },
    "bescom": {
        "gstin": "29AAACB0561N1Z5",
        "address": "KR Circle, Bangalore, 560001",
        "lat": 12.9716, "lon": 77.5946,
        "category": "utility"
    },
    "naturals basweswara n": {
        "gstin": "29AAIFN4521P1Z9",
        "address": "Basaveshwara Nagar, Bangalore",
        "lat": 12.9831, "lon": 77.5349,
        "category": "retail"
    }
}

def get_coords_from_address(address: str):
    """Mock geocoder: Deterministic lat/lon from address hash."""
    h = hashlib.md5(address.encode()).hexdigest()
    lat = 12.9716 + (int(h[:4], 16) / 65535.0 - 0.5) * 0.05
    lon = 77.5946 + (int(h[4:8], 16) / 65535.0 - 0.5) * 0.05
    return lat, lon

def generate_seaborn_map(user_lat, user_lon, verified_merchants, output_path="merchant_map.png"):
    """Generate a high-fidelity spatial plot using Seaborn in UTM meters."""
    data = []
    
    # User point in UTM
    u_east, u_north, zone_num, zone_let = utm.from_latlon(user_lat, user_lon)
    data.append({
        "Name": "YOU",
        "Easting": u_east,
        "Northing": u_north,
        "Type": "User",
        "Label": "HOME"
    })
    
    # Merchant points in UTM
    for m_id, info in verified_merchants.items():
        m_east, m_north, _, _ = utm.from_latlon(info['lat'], info['lon'])
        data.append({
            "Name": m_id.title(),
            "Easting": m_east,
            "Northing": m_north,
            "Type": "Merchant",
            "Label": info.get('gstin', 'Verified')
        })
        
    df = pd.DataFrame(data)
    
    plt.figure(figsize=(10, 8))
    sns.set_theme(style="whitegrid")
    
    # Plot Easting vs Northing (Meters)
    plot = sns.scatterplot(
        data=df, x="Easting", y="Northing", 
        hue="Type", style="Type", s=200, 
        palette={"User": "red", "Merchant": "blue"}
    )
    
    # Label points
    for i in range(df.shape[0]):
        plt.text(df.Easting[i]+5, df.Northing[i]+5, df.Name[i], 
                 fontsize=9, weight='bold' if df.Type[i] == 'User' else 'normal')

    plt.title("AXIOM NEIGHBORHOOD TRUST CLUSTER (UTM METERS)")
    plt.xlabel("Easting (m)")
    plt.ylabel("Northing (m)")
    plt.tight_layout()
    plt.savefig(output_path)
    print(f"\n✓ Spatial Map Saved to: {output_path}")

async def run_axiom_pipeline(user_id: str, aa_data: dict, user_loc: Location):
    """Direct implementation with Merchant Resolution."""
    
    transactions_raw = []
    for account in aa_data.get("accounts", []):
        transactions_raw.extend(account.transactions)

    # 1. Universal Extraction for All Counterparties (Business & Personal)
    for txn in transactions_raw:
        desc = (txn.description or "").upper()
        
        # Treat as Candidate
        match = re.search(r"UPI/(?:P2M|P2A)/\d+/([^/]+)/", txn.counterparty_name or "", re.IGNORECASE)
        if match:
            txn.counterparty_name = match.group(1).strip().lower()
        else:
            # Fallback greedy extraction for POS / ECOM / Other
            if "ECOM PUR/" in desc:
                parts = desc.split("/")
                if len(parts) > 1:
                    txn.counterparty_name = parts[1].strip().lower()
            elif "POS/" in desc:
                parts = desc.split("/")
                if len(parts) > 1:
                    txn.counterparty_name = parts[1].strip().lower()
            else:
                # Use raw counterparty or description
                raw = txn.counterparty_name if txn.counterparty_name and txn.counterparty_name != "-" else txn.description
                if raw:
                    txn.counterparty_name = raw.split("/")[0].strip().lower()

    upi_parser = UPIParser()
    recurring_patterns = await upi_parser.extract_recurring(
        [t.__dict__ for t in transactions_raw]
    )

    # 2. Resolve Verified Merchants
    print("-> Resolving Merchant GSTINs & Addresses...")
    verified_found = {}
    merchants_for_index = {}
    merchant_meta = {}
    
    for p in recurring_patterns:
        if p.payee_vpa in MERCHANT_REGISTRY:
            reg = MERCHANT_REGISTRY[p.payee_vpa]
            verified_found[p.payee_vpa] = reg
            merchants_for_index[p.payee_vpa] = Location(reg['lat'], reg['lon'], reg['address'])
            merchant_meta[p.payee_vpa] = {"category": reg['category'], "transaction_count": p.count}

    # 3. Spatial Indexing (KDTree)
    enricher = KDTreeEnricher(search_radius_km=20.0)
    if merchants_for_index:
        enricher.index_merchants(merchants_for_index, merchant_meta)
    
    enriched_node = await enricher.enrich_node(user_id, user_loc, node_type="user")

    # 4. Scoring Logic
    baseline_scorer = BaselineScorer()
    s_b = baseline_scorer.score(BaselineFeatures(
        income_volatility_index=0.3,
        expense_to_income_ratio=0.7,
        utility_payment_delta_avg=3.0,
        rent_consistency_months=6,
        merchant_density_score=enriched_node.merchant_density,
        informal_credit_proxy_count=1,
    ))

    ensemble = AxiomEnsemble()
    final_score = ensemble.compute_final_score(
        s_b=s_b, s_t=0.6, r_f=0.05,
        signal_count=len(recurring_patterns), user_id=user_id,
    )

    explainer = SHAPExplainer()
    reasons = await explainer.explain(
        axiom_score=final_score.axiom_score,
        component_scores=final_score.component_scores,
        features={
            "merchant_density": enriched_node.merchant_density,
            "neighborhood_diversity": enriched_node.neighborhood_diversity
        },
    )

    return final_score, reasons, enriched_node, verified_found

async def main():
    print("\n" + "="*55)
    print("  AXIOM CREDIT ENGINE - NEIGHBORHOOD GEOSPATIAL AUDIT")
    print("="*55)
    
    address = input("Enter User Location (Area/Pincode): ")
    u_lat, u_lon = get_coords_from_address(address)
    user_loc = Location(u_lat, u_lon, address)
    
    file_path = "test_data1.csv"
    user_id = "tejas_axiom_demo"
    
    with open(file_path, "r") as f:
        csv_content = f.read()
    
    ingestor = StatementIngestor()
    transactions = ingestor.parse_csv(csv_content, skip_header_lines=19)
    aa_data = ingestor.create_snapshot(user_id, transactions)
    
    print(f"\n[1/3] Processing Bank Statement...")
    print(f"[2/3] Resolving GSTINs and UTM Mapping...")
    score, reasons, enriched, verified = await run_axiom_pipeline(user_id, aa_data, user_loc)
    
    print(f"[3/3] Generating Spatial Plot...")
    generate_seaborn_map(u_lat, u_lon, verified)
    
    print("\n" + "="*55)
    print(f" FINAL AXIOM SCORE: {score.axiom_score} ({score.tier})")
    print(f" CONFIDENCE: {score.confidence_interval*100:.1f}%")
    print("="*55)
    
    print("\nRESOLVED LOCAL MERCHANTS:")
    print(f"{'MERCHANT':<20} | {'GSTIN':<15} | {'ADDRESS'}")
    print("-" * 55)
    for m_id, info in verified.items():
        print(f"{m_id.title()[:20]:<20} | {info['gstin']:<15} | {info['address']}")
    
    print("\nBEHAVIORAL REASONS (SHAP):")
    for r in reasons:
        symbol = "✔" if r.driver_type == "positive" else "✘"
        print(f" {symbol} {r.feature}: {r.explanation}")
    print("="*55 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
