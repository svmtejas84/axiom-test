import time
import requests
import sys
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.live import Live
from rich import box

console = Console()

API_URL = "http://127.0.0.1:8000"

def check_health():
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data
    except:
        return None

def main():
    console.clear()
    console.print(Panel.fit("[bold blue]AXIOM EQUILIBRIUM ENGINE[/bold blue]\n[dim]Production-Grade Credit Scoring Orchestrator[/dim]", border_style="blue", box=box.DOUBLE))

    # 1. Health Check
    with console.status("[bold green]Verifying Backend Infrastructure...") as status:
        health = check_health()
        if not health:
            console.print("[bold red]ERROR: Backend API is not reachable. Please start the server with 'uvicorn api.main:app'[/bold red]")
            sys.exit(1)
        
        console.print(f"[bold green]✓[/bold green] API Status: {health['status'].upper()}")
        for comp, state in health['components'].items():
            color = "green" if state == "ok" else "yellow" if state == "degraded" else "red"
            console.print(f"  - {comp:<10}: [{color}]{state.upper()}[/{color}]")

    from rich.prompt import Prompt, Confirm

    # 2. Gather User Data & Input Method
    console.print("\n[bold magenta]1. Identity & Data Source Selection[/bold magenta]")
    user_id = Prompt.ask("Enter User ID", default="user_demo_789")
    
    console.print("Data Input Methods:\n 1. UPI ID\n 2. Phone Number (Account Aggregator)\n 3. Document Upload (PDF/CSV)")
    input_method = Prompt.ask("Select Primary Data Stream", choices=["1", "2", "3"], default="1")
    
    import os
    import subprocess
    
    file_path_to_score = None
    payload = {}

    if input_method == "1":
        upi = Prompt.ask("Enter UPI ID", default="tejas@upi")
        payload["upi_id"] = upi
        
        # Resolve mock path via REPUTATION_NODES
        from examples.reputation_nodes import REPUTATION_NODES
        # Resolve matching key from REPUTATION_NODES
        resolved_key = None
        for key, node in REPUTATION_NODES.items():
            if node.get("vpa") == upi:
                resolved_key = key
                break

        # Map specific keys to requested neighborhood CSVs
        if resolved_key == "student_high":
            mock_path = "examples/high_trust_neighborhood.csv"
        elif resolved_key == "student_med":
            mock_path = "examples/medium_trust_neighborhood.csv"
        elif resolved_key == "student_low":
            mock_path = "examples/low_trust_neighborhood.csv"
        elif resolved_key and (resolved_key.startswith("parent") or resolved_key.startswith("landlord")):
            mock_path = None # Do not parse CSVs for these
        else:
            mock_path = f"examples/{upi.split('@')[0]}.csv"
        
        if mock_path and os.path.exists(mock_path):
            file_path_to_score = mock_path
            msg = f"Found mock data for {resolved_key}" if resolved_key else "Found mock data for UPI"
            console.print(f"[dim]{msg}: {mock_path}[/dim]")
        else:
            file_path_to_score = "test_data1.csv"
            if resolved_key and (resolved_key.startswith("parent") or resolved_key.startswith("landlord")):
                 console.print(f"[dim]Using reputation score for {resolved_key}. Falling back to default statement for behavioral analysis.[/dim]")
            else:
                 console.print(f"[dim]No specific mock data found. Falling back to default: {file_path_to_score}[/dim]")

    elif input_method == "2":
        phone = Prompt.ask("Enter Phone Number", default="9876543210")
        payload["phone_number"] = phone
        mock_path = f"examples/{phone}.csv"
        if os.path.exists(mock_path):
            file_path_to_score = mock_path
            console.print(f"[dim]Found mock data for Phone: {mock_path}[/dim]")
        else:
            file_path_to_score = "test_data1.csv"
            console.print(f"[dim]No specific mock data found. Falling back to default: {file_path_to_score}[/dim]")

    else:
        file_path_to_score = Prompt.ask("Enter absolute or relative path to CSV statement", default="test_data1.csv")
        if not os.path.exists(file_path_to_score):
            console.print(f"[bold red]Error: File {file_path_to_score} does not exist.[/bold red]")
            sys.exit(1)
        console.print(f"[dim]Document '{file_path_to_score}' accepted.[/dim]")

    # 3. Specialized Verification Modules
    console.print("\n[bold magenta]2. Specialized Verification Modules[/bold magenta]")
    
    parent_vpa = None
    if Confirm.ask("Link Parent VPA for Trust Inheritance?", default=True):
        parent_vpa = Prompt.ask("Enter Parent VPA", default="parent_prime@axis")

    student_verified = False
    do_student_verif = Confirm.ask("Initiate Student Verification?", default=True)
    if do_student_verif:
        edu_email = Prompt.ask("Enter Institutional Email", default="tejas@nmit.ac.in")
        console.print(f"[dim]Submitting student data for {edu_email}...[/dim]")
        try:
            resp = requests.post(f"{API_URL}/verify/student", json={
                "user_id": user_id,
                "edu_email": edu_email,
                "parents_vpa": parent_vpa or "parent@sbi",
                "first_name": "Tejas",
                "last_name": "H",
                "birth_date": "2000-01-01",
                "organization_id": 1,
                "organization_name": "NMIT"
            })
            if resp.status_code == 200:
                console.print(f"[bold green]✓[/bold green] Verification Status: {resp.json().get('status', 'Unknown')}")
                student_verified = True
            else:
                try:
                    error_detail = resp.json().get('detail', resp.text)
                except:
                    error_detail = resp.text or "Internal Server Error"
                console.print(f"[bold red]✗ Verification Rejected ({resp.status_code}): {error_detail}[/bold red]")
        except Exception as e:
            console.print(f"[bold red]✗ API Error: {e}[/bold red]")

    rent_verified = False
    landlord_vpa = None
    do_rent_verif = Confirm.ask("Initiate Rent Verification (OCR)?", default=False)
    if do_rent_verif:
        landlord_vpa = Prompt.ask("Enter Landlord VPA", default="prop_mgmt_corp@hdfc")
        console.print("[dim]Simulating OCR processing of Rent Agreement...[/dim]")
        time.sleep(1)
        console.print("[bold green]✓[/bold green] Rent Agreement Verified. High-Trust Signal added.")
        rent_verified = True

    # 4. Trigger Evaluation (Sandbox Pipeline)
    console.print("\n[bold blue][+][/bold blue] Triggering Equilibrium Engine for: [bold cyan]" + user_id + "[/bold cyan]")
    
    try:
        # Run the stateless pipeline
        cmd = ["python", "axiom_merchant_sandbox/run_axiom_stateless.py", file_path_to_score]
        if student_verified:
            cmd.append("--student-verified")
        if rent_verified:
            cmd.append("--rent-verified")
        if parent_vpa:
            cmd.extend(["--parent-vpa", parent_vpa])
        if landlord_vpa:
            cmd.extend(["--landlord-vpa", landlord_vpa])
            
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Pipeline Failed with exit code: {e.returncode}[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Failed to execute pipeline: {e}[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
