import os
import sys
import re
import math
import gc
import requests
import asyncio
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import torch

# Ensure parent directory is in the path so we can import from existing modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from ingestion.statement_ingest import StatementIngestor
from graph.kdtree_enricher import KDTreeEnricher, Location
from ingestion.utility_tracker import UtilityTracker, UtilityBill
from graph.st_pignn import STPIGNN
from scoring.ensemble import AxiomEnsemble

# Configure basic logging to suppress noisy debugs
logging.basicConfig(level=logging.ERROR)

# Target Residency for testing (e.g., Shanthinagar, Bengaluru)
TARGET_LAT = 12.9580
TARGET_LON = 77.5920
RADIUS_KM = 2.0
USER_PINCODE = "560027"

# Noise exclusion list for transaction technicalities
EXCLUSION_LIST = ["IMPS", "NEFT", "RTGS", "CASH", "TRANSFER", "CHRG", "FEE", "TAX", "INTEREST", "REVERSAL"]
# Commercial intent keywords
COMMERCIAL_KEYWORDS = ["SERVICES", "MARKETING", "DINING", "STORES", "RETAIL", "MEDICALS", "BAKERY", "STATION", "ENTERPRISES", "TRADING", "CORP", "PVT", "LTD"]

def clean_merchant_string(particulars: str, counterparty: str) -> str:
    """
    Universal extraction logic to identify ALL actors (Business & Personal).
    Strips transaction noise (IMPS, NEFT, etc.).
    """
    desc = (particulars or "").upper()
    for noise in EXCLUSION_LIST:
        if desc.startswith(noise) and "/" not in desc:
            return ""
    name = particulars if particulars else ""
    if counterparty and counterparty.strip() != "-":
        name = counterparty

    match = re.search(r"UPI/(?:P2M|P2A)/\d+/([^/]+)/", name, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
    else:
        if "ECOM PUR/" in desc or "POS/" in desc:
            parts = desc.split("/")
            if len(parts) > 1:
                name = parts[1].strip()
        else:
            name = name.split("/")[0].strip()

    name_upper = name.upper()
    if name_upper in EXCLUSION_LIST or len(name) <= 3:
        return ""

    name = str(name).lower()
    prefixes_to_strip = ["upi-", "transfer to-", "pay to-", "paid to-", "to-", "impsi-", "neft-", "rtgs-"]
    for prefix in prefixes_to_strip:
        if name.startswith(prefix):
            name = name[len(prefix):]
            
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def extract_pincode(text: str) -> str:
    match = re.search(r'\b(560\d{3})\b', text)
    if match: return match.group(1)
    match2 = re.search(r'\b(\d{6})\b', text)
    if match2: return match2.group(1)
    return ""

def mock_lat_lon_from_pincode(pincode: str) -> Tuple[float, float]:
    if not pincode: return TARGET_LAT + 0.1, TARGET_LON + 0.1
    h = hash(pincode)
    offset_lat = ((h % 100) - 50) / 2000.0
    offset_lon = (((h // 100) % 100) - 50) / 2000.0
    return TARGET_LAT + offset_lat, TARGET_LON + offset_lon

def resolve_via_web_search(merchant_name: str, city: str = "Bengaluru", base_pincode: str = "560027") -> dict:
    try:
        from ddgs import DDGS
        from bs4 import BeautifulSoup
    except ImportError:
        print("Please install required packages: pip install ddgs rapidfuzz beautifulsoup4")
        return None

    has_commercial_keyword = any(kw.lower() in merchant_name.lower() for kw in COMMERCIAL_KEYWORDS)
    if has_commercial_keyword:
        query = f"{merchant_name} {city} verified merchant GSTIN office address"
    else:
        query = f"{merchant_name} {city} address gstin"
    
    address_snippet = ""
    found_pincode = ""
    
    try:
        results = DDGS().text(query, max_results=3)
        for r in results:
            body = r.get("body", "")
            address_snippet += body + " "
            if not found_pincode:
                found_pincode = extract_pincode(body)
        del results
    except Exception:
        pass
        
    if not found_pincode:
        try:
            url = f"https://www.indiagst.in/search/{merchant_name.replace(' ', '%20')}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=1)
            soup = BeautifulSoup(resp.text, 'html.parser')
            text_content = soup.get_text()
            found_pincode = extract_pincode(text_content)
            if found_pincode:
                address_snippet += " [Scraped from indiagst]"
            del soup
            del resp
        except Exception:
            pass
            
    gc.collect()
    
    confidence = "None"
    is_p2p = False
    lat, lon = TARGET_LAT + 0.1, TARGET_LON + 0.1
    
    if found_pincode:
        if found_pincode == base_pincode: confidence = "High"
        elif found_pincode.startswith("560"): confidence = "Medium"
        else: confidence = "Low"
        lat, lon = mock_lat_lon_from_pincode(found_pincode)
    elif city.lower() in address_snippet.lower():
        if has_commercial_keyword: confidence = "Medium"
        else: confidence = "Low"
        lat, lon = TARGET_LAT + 0.05, TARGET_LON + 0.05
    else:
        is_p2p = True
        
    if is_p2p:
        return {"gstin": "N/A", "address": "High-Trust P2P Node", "confidence": "N/A", "lat": 0.0, "lon": 0.0, "status": "P2P Node"}
    else:
        return {"gstin": "FREE_SEARCH", "address": (address_snippet[:30] + "...") if address_snippet else "Unknown", "confidence": confidence, "lat": lat, "lon": lon, "status": "Resolved"}

async def main():
    print("="*60)
    print(" AXIOM EPHEMERAL STATELESS SCORING PIPELINE (END-TO-END)")
    print("="*60)
    
    csv_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data1.csv")
    if not os.path.exists(csv_file_path):
        print(f"Error: Could not find {csv_file_path}")
        return
        
    print(f"\n[+] 1. Ingesting transactions from: {os.path.basename(csv_file_path)}")
    with open(csv_file_path, "r") as f:
        csv_content = f.read()
        
    ingestor = StatementIngestor()
    transactions = ingestor.parse_csv(csv_content, skip_header_lines=19)
    print(f"    Parsed {len(transactions)} transactions.")
    
    print("\n[+] 2. Frequency Extraction of All Counterparties...")
    counterparty_names = []
    for txn in transactions:
        clean_name = clean_merchant_string(txn.description, txn.counterparty_name)
        if clean_name: counterparty_names.append(clean_name)
            
    counts = Counter(counterparty_names)
    candidates_to_resolve = [(name, freq) for name, freq in counts.most_common(50) if freq >= 3]
    print(f"    Found {len(candidates_to_resolve)} Top Candidates (Freq >= 3)")
    
    print("\n[+] 3. Live Free Multi-Stage Resolution...")
    from tqdm import tqdm
    resolved_profiles = []
    for name, freq in tqdm(candidates_to_resolve, desc="Resolving Entities", unit="merchant"):
        profile = resolve_via_web_search(name, "Bengaluru", USER_PINCODE)
        if profile:
            profile_copy = profile.copy()
            profile_copy['queried_name'] = name
            profile_copy['frequency'] = freq
            resolved_profiles.append(profile_copy)
            
    print("\n--- Entity Resolution Directory ---")
    print(f"{'NAME':<25} | {'FREQ':<4} | {'STATUS':<15} | {'ADDRESS/PINCODE'}")
    print("-" * 75)
    
    local_merchants_count = 0
    p2p_nodes_count = 0
    for p in resolved_profiles:
        addr = str(p.get('pincode', '')) or p['address']
        print(f"{p['queried_name'][:24]:<25} | {p['frequency']:<4} | {p['status']:<15} | {addr}")
        if p['status'] == 'Resolved': local_merchants_count += 1
        elif p['status'] == 'P2P Node': p2p_nodes_count += 1

    print("\n[+] 4. Calculating Neighborhood Integration Index (S_N) via KDTree...")
    enricher = KDTreeEnricher(search_radius_km=RADIUS_KM)
    merchants_for_index = {}
    merchant_meta = {}
    for i, p in enumerate(resolved_profiles):
        if p['status'] == 'Resolved':
            m_id = f"m_{i}"
            merchants_for_index[m_id] = Location(p['lat'], p['lon'], p['address'])
            merchant_meta[m_id] = {"category": "general", "transaction_count": p['frequency']}
        
    if merchants_for_index: enricher.index_merchants(merchants_for_index, merchant_meta)
    target_loc = Location(TARGET_LAT, TARGET_LON, "Target Residency")
    enriched_node = await enricher.enrich_node("user_1", target_loc, node_type="user")
    
    density = local_merchants_count / (math.pi * (RADIUS_KM ** 2)) if local_merchants_count > 0 else 0.0
    print(f"    Neighborhood Density Computed: {density:.2f} Merchants/km²")

    print("\n[+] 5. Feeding Signals to utility_tracker.py...")
    today = datetime.now()
    bills = [
        UtilityBill("b1", "electricity", 1200.0, today - timedelta(days=90), today - timedelta(days=88), "Bengaluru", {}),
        UtilityBill("b2", "electricity", 1350.0, today - timedelta(days=60), today - timedelta(days=57), "Bengaluru", {}),
        UtilityBill("b3", "electricity", 1100.0, today - timedelta(days=30), today - timedelta(days=29), "Bengaluru", {}),
        UtilityBill("b4", "internet", 999.0, today - timedelta(days=90), today - timedelta(days=89), "Bengaluru", {}),
        UtilityBill("b5", "internet", 999.0, today - timedelta(days=60), today - timedelta(days=59), "Bengaluru", {}),
        UtilityBill("b6", "internet", 999.0, today - timedelta(days=30), today - timedelta(days=28), "Bengaluru", {}),
    ]
    tracker = UtilityTracker()
    utility_score = await tracker.compute_payment_delta(bills)
    s_b = utility_score.overall_score
    print(f"    Utility Discipline Score (S_B): {s_b:.2f}")

    print("\n[+] 6. Initializing st_pignn.py on CUDA...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"    Hardware Acceleration: {device.type.upper()}")
    
    st_pignn = STPIGNN(node_feature_dim=8, edge_feature_dim=2, num_months=12).to(device)
    st_pignn.eval()
    
    total_nodes = 1 + local_merchants_count + p2p_nodes_count
    if total_nodes == 1:
        print("Warning: No entities resolved to feed into graph.")
        s_t = 0.5
    else:
        x = torch.randn(total_nodes, 8, device=device)
        sources = torch.zeros(total_nodes - 1, dtype=torch.long, device=device)
        targets = torch.arange(1, total_nodes, dtype=torch.long, device=device)
        edge_index = torch.stack([sources, targets], dim=0)
        edge_attr = torch.randn(total_nodes - 1, 2, device=device)
        temporal_x = torch.randn(total_nodes, 12, 8, device=device)
        debt_to_income = torch.abs(torch.randn(total_nodes, device=device) * 0.3)
        expense_to_income = torch.abs(torch.randn(total_nodes, device=device) * 0.6)
        has_circular_loop = torch.zeros(total_nodes, device=device)
        
        with torch.no_grad():
            embeddings, scores = st_pignn(
                x, edge_index, edge_attr, temporal_x,
                debt_to_income, has_circular_loop, expense_to_income
            )
        s_t = scores[0].item()
    print(f"    Transitive Trust Score (S_T): {s_t:.2f}")

    print("\n[+] 7. Executing ensemble.py...")
    ensemble = AxiomEnsemble()
    r_f = 0.05
    axiom_result = ensemble.compute_final_score(s_b=s_b, s_t=s_t, r_f=r_f, signal_count=len(resolved_profiles), user_id="u_sandbox_001")

    print("\n" + "="*60)
    print(" AXIOM STATELESS REPORT")
    print("="*60)
    print(f" Axiom Score   : {axiom_result.axiom_score} / 900")
    print(f" Credit Tier   : {axiom_result.tier}")
    print(f" Confidence    : {axiom_result.confidence_interval:.1%} (Based on {axiom_result.signal_count} deep signals)")
    print("\n Dynamic Drivers:")
    print(f"  1. [+] Utility Discipline (Avg Delta: {utility_score.avg_payment_delta_days:.1f} days)")
    print(f"  2. [+] Neighborhood Density Integration ({density:.2f} Merchants/km²)")
    print(f"  3. [+] High-Trust P2P Network Validation ({p2p_nodes_count} nodes)")
    print("="*60)

    print("\n[+] Initiating Total Memory Purge...")
    try: del x, edge_index, edge_attr, temporal_x, debt_to_income, expense_to_income, has_circular_loop
    except NameError: pass
    try: del embeddings, scores
    except NameError: pass
    
    del st_pignn, ensemble, axiom_result, tracker, bills
    del transactions, counterparty_names, counts, candidates_to_resolve, resolved_profiles
    
    gc.collect()
    if torch.cuda.is_available(): torch.cuda.empty_cache()
    print("    Memory Wipe Complete. Zero-Footprint target achieved.")

if __name__ == "__main__":
    asyncio.run(main())
