import os
import sys
import re
import math
import gc
import requests
from collections import Counter
from typing import List, Dict, Any, Tuple

# Ensure parent directory is in the path so we can import from existing modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from ingestion.statement_ingest import StatementIngestor
from graph.kdtree_enricher import KDTreeEnricher, Location
import asyncio

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
    
    # Noise Filter: Skip if the name is just a transaction type
    for noise in EXCLUSION_LIST:
        if desc.startswith(noise) and "/" not in desc:
            return ""
            
    name = particulars if particulars else ""
    if counterparty and counterparty.strip() != "-":
        name = counterparty

    # Treat as Candidate
    match = re.search(r"UPI/(?:P2M|P2A)/\d+/([^/]+)/", name, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
    else:
        if "ECOM PUR/" in desc:
            parts = desc.split("/")
            if len(parts) > 1:
                name = parts[1].strip()
        elif "POS/" in desc:
            parts = desc.split("/")
            if len(parts) > 1:
                name = parts[1].strip()
        else:
            name = name.split("/")[0].strip()

    # Final Noise Check on extracted name
    name_upper = name.upper()
    if name_upper in EXCLUSION_LIST or len(name) <= 3:
        return ""

    name = str(name).lower()
    prefixes_to_strip = [
        "upi-", "transfer to-", "pay to-", "paid to-", "to-", 
        "impsi-", "neft-", "rtgs-"
    ]
    
    for prefix in prefixes_to_strip:
        if name.startswith(prefix):
            name = name[len(prefix):]
            
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def extract_pincode(text: str) -> str:
    """Extract a 6 digit Indian pincode, preferring Bengaluru 560xxx"""
    match = re.search(r'\b(560\d{3})\b', text)
    if match: return match.group(1)
    match2 = re.search(r'\b(\d{6})\b', text)
    if match2: return match2.group(1)
    return ""

def mock_lat_lon_from_pincode(pincode: str) -> Tuple[float, float]:
    """Deterministic hash mapping of pincode to local coordinates"""
    if not pincode:
        return TARGET_LAT + 0.1, TARGET_LON + 0.1
    h = hash(pincode)
    offset_lat = ((h % 100) - 50) / 2000.0
    offset_lon = (((h // 100) % 100) - 50) / 2000.0
    return TARGET_LAT + offset_lat, TARGET_LON + offset_lon

def resolve_via_web_search(merchant_name: str, city: str = "Bengaluru", base_pincode: str = "560027") -> dict:
    """
    Multi-stage free web search resolution strategy with P2P Fallback.
    Adds commercial keyword verification.
    """
    try:
        from ddgs import DDGS
        from bs4 import BeautifulSoup
    except ImportError:
        print("Please install required packages: pip install ddgs rapidfuzz beautifulsoup4")
        return None

    result = None
    
    # Enhanced query if commercial keywords are present
    has_commercial_keyword = any(kw.lower() in merchant_name.lower() for kw in COMMERCIAL_KEYWORDS)
    if has_commercial_keyword:
        query = f"{merchant_name} {city} verified merchant GSTIN office address"
    else:
        query = f"{merchant_name} {city} address gstin"
    
    address_snippet = ""
    found_pincode = ""
    
    # Stage 1: DDGS Search
    try:
        results = DDGS().text(query, max_results=3)
        for r in results:
            body = r.get("body", "")
            address_snippet += body + " "
            if not found_pincode:
                found_pincode = extract_pincode(body)
        
        # Zero-footprint 
        del results
    except Exception as e:
        pass
        
    # Stage 2: Fallback Directory Scraping
    if not found_pincode:
        try:
            url = f"https://www.indiagst.in/search/{merchant_name.replace(' ', '%20')}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
            resp = requests.get(url, headers=headers, timeout=1)
            soup = BeautifulSoup(resp.text, 'html.parser')
            text_content = soup.get_text()
            found_pincode = extract_pincode(text_content)
            if found_pincode:
                address_snippet += " [Scraped from indiagst]"
            
            # Zero-footprint
            del soup
            del resp
        except Exception:
            pass
            
    # Force Garbage Collection for zero-footprint enforcement
    gc.collect()
    
    # Stage 3: Spatial Filtering & Personal/Landlord Logic
    confidence = "None"
    is_p2p = False
    lat, lon = TARGET_LAT + 0.1, TARGET_LON + 0.1 # Default out of bounds
    
    if found_pincode:
        # Pincode Match -> High Confidence
        if found_pincode == base_pincode:
            confidence = "High"
        elif found_pincode.startswith("560"):
            confidence = "Medium"
        else:
            confidence = "Low"
            
        lat, lon = mock_lat_lon_from_pincode(found_pincode)
    elif city.lower() in address_snippet.lower():
        # Only City Match
        if has_commercial_keyword:
            confidence = "Medium" # Boost if it has a commercial name
        else:
            confidence = "Low"
        lat, lon = TARGET_LAT + 0.05, TARGET_LON + 0.05
    else:
        # High-frequency node without GST/Business presence -> likely P2P/Landlord
        is_p2p = True
        
    if is_p2p:
        result = {
            "gstin": "N/A",
            "address": "High-Trust P2P Node",
            "confidence": "N/A",
            "lat": 0.0,
            "lon": 0.0,
            "status": "P2P Node"
        }
    else:
        result = {
            "gstin": "FREE_SEARCH",
            "address": (address_snippet[:30] + "...") if address_snippet else "Unknown",
            "confidence": confidence,
            "lat": lat,
            "lon": lon,
            "status": "Resolved"
        }
        
    return result

async def main():
    print("="*60)
    print(" AXIOM FREQUENCY-BASED ENTITY RESOLUTION SCAN")
    print("="*60)
    
    csv_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data1.csv")
    
    if not os.path.exists(csv_file_path):
        print(f"Error: Could not find {csv_file_path}")
        return
        
    print(f"\n1. Ingesting transactions from: {os.path.basename(csv_file_path)}")
    with open(csv_file_path, "r") as f:
        csv_content = f.read()
        
    ingestor = StatementIngestor()
    transactions = ingestor.parse_csv(csv_content, skip_header_lines=19)
    print(f"✓ Parsed {len(transactions)} transactions.")
    
    print("\n2. Frequency Extraction of All Counterparties...")
    counterparty_names = []
    for txn in transactions:
        clean_name = clean_merchant_string(txn.description, txn.counterparty_name)
        if clean_name:
            counterparty_names.append(clean_name)
            
    # Frequency Analysis Layer
    counts = Counter(counterparty_names)
    
    # Top 50 Most Frequent Counterparties (3+ transactions)
    candidates_to_resolve = [(name, freq) for name, freq in counts.most_common(50) if freq >= 3]
    
    print(f"✓ Total Unique Names Scanned: {len(counts)}")
    print(f"✓ Found {len(candidates_to_resolve)} Top Candidates (Freq >= 3)")
    
    print("\n--- Top Frequent Names ---")
    for name, freq in candidates_to_resolve[:10]: # Print top 10 for brevity
        print(f" - {name[:30]:<30}: {freq} txns")
    if len(candidates_to_resolve) > 10:
        print(f" ... and {len(candidates_to_resolve) - 10} more.")
    
    print(f"\n3. Live Free Multi-Stage Resolution...")
    
    try:
        from tqdm import tqdm
    except ImportError:
        print("Please install tqdm: pip install tqdm")
        return
        
    resolved_profiles = []
    # Added tqdm for progress bar
    for name, freq in tqdm(candidates_to_resolve, desc="Resolving Entities", unit="merchant"):
        profile = resolve_via_web_search(name, "Bengaluru", USER_PINCODE)
        if profile:
            profile_copy = profile.copy()
            profile_copy['queried_name'] = name
            profile_copy['frequency'] = freq
            resolved_profiles.append(profile_copy)
            
    print(f"✓ Evaluated {len(resolved_profiles)} frequent candidates.")
    
    print("\n--- Entity Resolution Directory ---")
    print(f"{'NAME':<25} | {'FREQ':<4} | {'STATUS':<15} | {'ADDRESS/PINCODE'}")
    print("-" * 75)
    
    local_merchants_count = 0
    p2p_nodes_count = 0
    for p in resolved_profiles:
        addr = str(p.get('pincode', '')) or p['address']
        print(f"{p['queried_name'][:24]:<25} | {p['frequency']:<4} | {p['status']:<15} | {addr}")
        
        if p['status'] == 'Resolved':
            local_merchants_count += 1
        elif p['status'] == 'P2P Node':
            p2p_nodes_count += 1

    print("\n4. Calculating Neighborhood Integration Index (S_N) via KDTree...")
    enricher = KDTreeEnricher(search_radius_km=RADIUS_KM)
    
    merchants_for_index = {}
    merchant_meta = {}
    for i, p in enumerate(resolved_profiles):
        if p['status'] == 'Resolved':
            m_id = f"m_{i}"
            merchants_for_index[m_id] = Location(p['lat'], p['lon'], p['address'])
            merchant_meta[m_id] = {"category": "general", "transaction_count": p['frequency']}
        
    if merchants_for_index:
        enricher.index_merchants(merchants_for_index, merchant_meta)
        
    target_loc = Location(TARGET_LAT, TARGET_LON, "Target Residency")
    enriched_node = await enricher.enrich_node("user_1", target_loc, node_type="user")
    
    s_n_score = enriched_node.economic_cluster_score * 100.0
    density = local_merchants_count / (math.pi * (RADIUS_KM ** 2)) if local_merchants_count > 0 else 0.0
    
    # Summary Logger
    print("\n" + "="*60)
    print(f" AXIOM UNIVERSAL SCAN SUMMARY LOGGER")
    print("="*60)
    print(f" Target Location (Lat, Lon) : {TARGET_LAT}, {TARGET_LON}")
    print(f" Evaluation Radius          : {RADIUS_KM} km")
    print(f" Total Unique Names Scanned : {len(counts)}")
    print(f" High-Freq Candidates       : {len(candidates_to_resolve)}")
    print(f" Local Merchants (S_N)      : {local_merchants_count}")
    print(f" High-Trust P2P Nodes (S_T) : {p2p_nodes_count}")
    print(f" Neighborhood Density       : {density:.2f} Merchants/km²")
    print(f" Neighborhood Trust (S_N)   : {s_n_score:.1f} / 100.0")
    print("="*60)
    
if __name__ == "__main__":
    asyncio.run(main())
