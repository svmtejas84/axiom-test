import time

# Mock GST API Database
MOCK_GST_DB = {
    "bangalore metro rail": {
        "gstin": "29AAACB4881D1ZQ",
        "legal_name": "BANGALORE METRO RAIL CORPORATION LIMITED",
        "address": "BMTC Complex, Shanthinagar, Bengaluru, 560027",
        "lat": 12.9592, 
        "lon": 77.5917,
    },
    "swiggy limited": {
        "gstin": "29AAECS4916L1ZM",
        "legal_name": "BUNDL TECHNOLOGIES PRIVATE LIMITED",
        "address": "No.55, Sy No.8-14, Ground Floor, Devarabeesanahalli, Varthur Hobli, Bengaluru",
        "lat": 12.9345,
        "lon": 77.6260, # Koramangala area, roughly ~5km from Shanthinagar
    },
    "orien sales": {
        "gstin": "29AAOCO8291P1ZV",
        "legal_name": "ORIEN SALES CORP",
        "address": "No 12, JC Road, Kalasipalyam, Bengaluru",
        "lat": 12.9620,
        "lon": 77.5850, # JC Road, roughly ~1km from Shanthinagar
    }
}

def fetch_gst_profile(merchant_name: str) -> dict:
    """
    Simulates a 'Search by Name' -> 'Fetch GST Profile' API flow.
    Returns a dictionary containing GSTIN, Address, Lat, and Lon if found.
    """
    clean_name = merchant_name.strip().lower()
    
    # Try exact match first
    if clean_name in MOCK_GST_DB:
        return MOCK_GST_DB[clean_name]
        
    # Try partial match (like a search)
    for db_name, profile in MOCK_GST_DB.items():
        if db_name in clean_name or clean_name in db_name:
            return profile
            
    return None
