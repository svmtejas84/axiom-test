# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Axiom Credit Platform - Windows Setup Script
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# This script installs all necessary dependencies for the Axiom
# Credit Platform on a fresh Windows system.
#
# Requirements:
#   - Windows 10/11
#   - PowerShell 5.1 or later (PowerShell 7 recommended)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$ErrorActionPreference = "Stop"

function Write-Header ($Text) {
    Write-Host "`n=== $Text ===" -ForegroundColor Cyan
}

function Write-Success ($Text) {
    Write-Host "[SUCCESS] $Text" -ForegroundColor Green
}

function Write-Info ($Text) {
    Write-Host "[INFO] $Text" -ForegroundColor White
}

function Write-Warning-Message ($Text) {
    Write-Host "[WARNING] $Text" -ForegroundColor Yellow
}

Write-Header "Axiom Credit Platform Setup"
Write-Info "Starting environment setup..."

# 1. Check for Winget
if (!(Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Error "winget is not installed. Please install 'App Installer' from the Microsoft Store."
}
Write-Success "winget found."

# 2. Install Git
if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Info "Installing Git..."
    winget install --id Git.Git -e --source winget --silent
    Write-Success "Git installed."
} else {
    Write-Success "Git already installed."
}

# 3. Install Python 3.11
if (!(Get-Command python -ErrorAction SilentlyContinue) -or (python --version) -notmatch "3.11") {
    Write-Info "Installing Python 3.11..."
    winget install --id Python.Python.3.11 -e --source winget --silent
    Write-Success "Python 3.11 installed. You may need to restart your terminal after this script."
} else {
    Write-Success "Python 3.11 already installed."
}

# 4. Install Poetry
if (!(Get-Command poetry -ErrorAction SilentlyContinue)) {
    Write-Info "Installing Poetry..."
    (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
    
    # Add Poetry to Path for current session
    $PoetryPath = "$env:APPDATA\Python\Scripts"
    if ($env:Path -notlike "*$PoetryPath*") {
        $env:Path += ";$PoetryPath"
    }
    Write-Success "Poetry installed."
} else {
    Write-Success "Poetry already installed."
}

# 5. Install Docker Desktop (for Postgres, Mongo, Redis)
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Info "Installing Docker Desktop... (This may take a while)"
    Write-Warning-Message "Note: Docker Desktop requires WSL 2 to be enabled."
    winget install --id Docker.DockerDesktop -e --source winget --silent
    Write-Success "Docker Desktop installed."
} else {
    Write-Success "Docker already installed."
}

# 6. Initialize Environment Variables
Write-Header "Project Initialization"
if (!(Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Info "Creating .env from .env.example..."
        Copy-Item ".env.example" ".env"
        Write-Success ".env created."
    } else {
        Write-Warning-Message ".env.example not found. Skipping .env creation."
    }
} else {
    Write-Success ".env already exists."
}

# 7. Install Python Dependencies
Write-Info "Installing project dependencies via Poetry..."
try {
    poetry install
    Write-Success "Python dependencies installed."
} catch {
    Write-Warning-Message "Poetry install failed. Ensure Python 3.11 is correctly linked to Poetry."
    Write-Info "Try running: poetry env use python3.11"
}

# 8. Final Instructions
Write-Header "Setup Complete!"
Write-Info "Next steps:"
Write-Info "1. Restart your terminal to ensure all PATH changes take effect."
Write-Info "2. Ensure Docker Desktop is running."
Write-Info "3. Start infrastructure:  docker-compose up -d"
Write-Info "4. Run the application:   poetry run python main_execution.py"
Write-Host "`nWelcome to Axiom!`n" -ForegroundColor Green
