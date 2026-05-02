import subprocess
import asyncio
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CSV_FILES = {
    "Low Trust": "examples/low_trust_neighborhood.csv",
    "Med Trust": "examples/medium_trust_neighborhood.csv",
    "High Trust": "examples/high_trust_neighborhood.csv"
}

SCENARIOS = [
    {"name": "Baseline (None)", "args": []},
    {"name": "Landlord Only", "args": ["--rent-verified", "--landlord-vpa", "prop_mgmt_corp@hdfc"]},
    {"name": "Student Only", "args": ["--student-verified", "--parent-vpa", "rahulpatil13-1@axis"]},
    {"name": "Full (Both)", "args": ["--student-verified", "--parent-vpa", "rahulpatil13-1@axis", "--rent-verified", "--landlord-vpa", "prop_mgmt_corp@hdfc"]}
]

def run_pipeline(csv_path, extra_args):
    cmd = ["python3", "axiom_merchant_sandbox/run_axiom_stateless.py", csv_path] + extra_args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Parse score from output: " Axiom Score   : 300 / 900"
        for line in result.stdout.splitlines():
            if "Axiom Score" in line:
                return line.split(":")[1].split("/")[0].strip()
    except Exception as e:
        return f"Error: {e}"
    return "N/A"

def main():
    print("| User Profile | Scenario | Axiom Score |")
    print("| :--- | :--- | :--- |")
    
    for profile_name, csv_path in CSV_FILES.items():
        for scenario in SCENARIOS:
            score = run_pipeline(csv_path, scenario["args"])
            print(f"| {profile_name} | {scenario['name']} | {score} |")

if __name__ == "__main__":
    main()
