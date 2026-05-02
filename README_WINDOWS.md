# Axiom Windows Setup

This directory contains a `setup_windows.ps1` script to automate the installation of all dependencies on a fresh Windows system.

## Prerequisites

- **Windows 10/11**
- **Administrator Privileges** (required for `winget` installations)

## How to Run

1. Open **PowerShell** as an **Administrator**.
2. Navigate to the project directory:
   ```powershell
   cd path\to\axiom-test
   ```
3. Set the execution policy to allow the script to run (if not already set):
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
   ```
4. Run the setup script:
   ```powershell
   .\setup_windows.ps1
   ```

## What the Script Does

- **Checks for winget**: The Windows Package Manager used for installations.
- **Installs Git**: Required for version control.
- **Installs Python 3.11**: The required Python version for this project.
- **Installs Poetry**: The dependency management tool.
- **Installs Docker Desktop**: Required for running PostgreSQL, MongoDB, and Redis.
- **Sets up .env**: Creates a local environment file from `.env.example`.
- **Installs Dependencies**: Runs `poetry install` to fetch all Python packages.

## Troubleshooting

- **PATH Issues**: If `poetry` or `python` are not recognized after installation, close and reopen your terminal.
- **Docker/WSL**: Docker Desktop requires WSL 2. If it prompts you to install WSL updates, follow the on-screen instructions from Microsoft.
- **Python Version**: If you have multiple Python versions, you may need to run `poetry env use python3.11` manually.
