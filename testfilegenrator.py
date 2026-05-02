import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_neighborhood_statement(profile_type, filename):
    rows = 2000
    start_date = datetime(2024, 5, 1)
    balance = 75000 if profile_type == 'high' else 15000
    
    # Neighborhood-specific merchants (local feel)
    local_merchants = [
        "Siddeshwara Kirana Store", "Amma Bakery", "SLV Refreshments", 
        "Shell Petrol Bunk", "Balaji Medicals", "Nandini Milk Parlour", 
        "Local Vegetable Vendor", "Laundry Service", "Auto-UPI Pay",
        "Fastrack Service Center", "Star Local Supermarket",
        "BESCOM Electricity Bill", "Airtel Broadband", "Jio Postpaid"
    ]
    
    data = []
    
    for i in range(rows):
        # Time distribution: 1-2 transactions per day
        current_date = start_date + timedelta(hours=i * 10)
        is_salary_day = (current_date.day == 1)
        
        # Default: Small local debit
        narration = np.random.choice(local_merchants)
        withdrawal = 0
        deposit = 0
        
        # Profile-specific logic
        if profile_type == 'high':
            # High Trust: Frequent local spends but high balance maintenance
            if i % 70 == 0: # Monthly credit
                deposit = np.random.uniform(90000, 110000)
                narration = "SALARY CREDIT - CORP"
            else:
                withdrawal = np.random.uniform(50, 1200) # Small neighborhood spends
                
        elif profile_type == 'medium':
            # Medium Trust: Highly frequent debits, lower credits
            if i % 150 == 0:
                deposit = np.random.uniform(30000, 45000)
                narration = "UPI-INWARD-TRANSFER"
            else:
                withdrawal = np.random.uniform(20, 2500)
                if np.random.random() < 0.1: # Occasional Swiggy/Zomato
                    narration = np.random.choice(["Zomato Pay", "Swiggy Order"])
                    
        else: # low trust
            # Low Trust: "Burn" profile. More debits than deposits, rapid depletion.
            if i % 250 == 0:
                deposit = np.random.uniform(10000, 20000)
                narration = "CASH DEPOSIT-CDM"
            else:
                withdrawal = np.random.uniform(100, 5000)
                # High-risk neighborhood merchants
                narration = np.random.choice([
                    "LOCAL WINE STORE", "ATM WITHDRAWAL", "FAILED-UPI-REV", 
                    "DREAM11-ENTRY", "CASH-OUT-AGENT"
                ])

        balance += (deposit - withdrawal)
        
        # Prevent negative balance for high/medium, allow for low (simulating bounce)
        if profile_type != 'low' and balance < 0:
            balance = np.random.uniform(100, 500)
            
        data.append({
            "Date": current_date.strftime("%d-%b-%Y %H:%M"),
            "Narration": narration,
            "Chq/Ref No": f"RR{np.random.randint(100000, 999999)}",
            "Withdrawal Amt": round(withdrawal, 2),
            "Deposit Amt": round(deposit, 2),
            "Closing Balance": round(balance, 2)
        })

    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"Generated {filename} with {rows} rows.")

# Execution
generate_neighborhood_statement('high', 'high_trust_neighborhood.csv')
generate_neighborhood_statement('medium', 'medium_trust_neighborhood.csv')
generate_neighborhood_statement('low', 'low_trust_neighborhood.csv')