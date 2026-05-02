# Run this script from PowerShell with administrator privileges.
# It installs Node.js LTS using winget and optionally starts the frontend.

param(
  [switch]$StartFrontend
)

# Check whether Node.js is already installed
$node = Get-Command node -ErrorAction SilentlyContinue
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($node -and $npm) {
  Write-Host "Node.js is already installed."
  Write-Host "Node version: $(node -v)"
  Write-Host "npm version: $(npm -v)"
} else {
  Write-Host "Node.js not present. Installing Node.js LTS via winget..."

  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Error "winget is not available. Install Node.js manually from https://nodejs.org/"
    exit 1
  }

  winget install --id OpenJS.NodeJS.LTS -e --silent --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    Write-Error "Node.js installation failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
  }

  Write-Host "Node.js installation finished."
  Write-Host "Reload your terminal or open a new one if node/npm are not available yet."

  $node = Get-Command node -ErrorAction SilentlyContinue
  $npm = Get-Command npm -ErrorAction SilentlyContinue
  if (-not $node -or -not $npm) {
    Write-Warning "node or npm not found in PATH. Please restart your terminal and run 'node -v' and 'npm -v'."
    exit 0
  }

  Write-Host "Node version: $(node -v)"
  Write-Host "npm version: $(npm -v)"
}

if ($StartFrontend) {
  Write-Host "Installing frontend dependencies..."
  Push-Location .
  npm install
  if ($LASTEXITCODE -ne 0) {
    Write-Error "npm install failed with exit code $LASTEXITCODE."
    Pop-Location
    exit $LASTEXITCODE
  }

  Write-Host "Starting Next.js frontend..."
  Start-Process -NoNewWindow npm -ArgumentList 'run', 'dev'
  Pop-Location
  Write-Host "Frontend started. Open http://localhost:3000 in your browser."
}
