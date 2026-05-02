REPUTATION_NODES = {
    # CATEGORY 1: STUDENTS (USER PROFILES)
    "student_high": {
        "node_id": "u_student_high",
        "reputation_score": 0.95,
        "email_domain": "ac.in",
        "typical_merchants": ["Medicals", "Stationery", "Library Fees", "University Cafeteria"],
        "risk_flags": 0,
        "type": "Student"
    },
    "student_med": {
        "node_id": "u_student_med",
        "reputation_score": 0.65,
        "email_domain": "ac.in",
        "typical_merchants": ["SLV Refreshments", "Amma Bakery", "Uber India", "Swiggy"],
        "risk_flags": 1,
        "type": "Student"
    },
    "student_low": {
        "node_id": "u_student_low",
        "reputation_score": 0.25,
        "email_domain": "gmail.com",
        "typical_merchants": ["Betting App", "Wine Store", "Local Bar", "Game Top-up"],
        "risk_flags": 8,
        "type": "Student"
    },

    # CATEGORY 2: PARENTS (TRUST INHERITANCE)
    "parent_high": {
        "node_id": "p_parent_high",
        "reputation_score": 0.98,
        "vpa": "rahulpatil13-1@axis",
        "typical_merchants": ["Property Tax", "Life Insurance", "Wealth Management", "School Fees"],
        "avg_daily_balance": "High",
        "type": "Parent"
    },
    "parent_med": {
        "node_id": "p_parent_med",
        "reputation_score": 0.70,
        "vpa": "kishore52@sbi",
        "typical_merchants": ["Supermarket", "Electric Bill", "Petrol Bunk", "Mobile Recharge"],
        "avg_daily_balance": "Medium",
        "type": "Parent"
    },
    "parent_low": {
        "node_id": "p_parent_low",
        "reputation_score": 0.30,
        "vpa": "pranit@upi",
        "typical_merchants": ["ATM Withdrawal", "Wine Store", "Cash-out Agent", "Collection Agency"],
        "avg_daily_balance": "Low",
        "type": "Parent"
    },

    # CATEGORY 3: LANDLORDS (STABILITY VALIDATION)
    "landlord_high": {
        "node_id": "l_landlord_high",
        "reputation_score": 0.99,
        "type": "Institutional",
        "vpa": "riya93@hdfc",
        "pattern": "Monthly fixed receipts (50+ count)",
        "gst_status": "Registered",
        "typical_merchants": ["Maintenance Services", "Property Tax", "Water Board"]
    },
    "landlord_med": {
        "node_id": "l_landlord_med",
        "reputation_score": 0.75,
        "type": "Private",
        "vpa": "ramesh67@icici",
        "pattern": "2-3 monthly rent receipts",
        "gst_status": "Unregistered",
        "typical_merchants": ["Hardware Store", "Paint Shop", "Grocery"]
    },
    "landlord_low": {
        "node_id": "l_landlord_low",
        "reputation_score": 0.40,
        "type": "Unverified",
        "vpa": "akshay82@okaxis",
        "pattern": "Inconsistent pattern",
        "gst_status": "Unregistered",
        "fraud_flags": 3
    }
}
