# Start the frontend from the frontend folder.
# Uses local portable Node if system Node/npm is not available.

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$systemNode = Get-Command node -ErrorAction SilentlyContinue
$systemNpm = Get-Command npm -ErrorAction SilentlyContinue

$portableRoot = Join-Path $scriptDir 'node-portable\node-v24.15.0-win-x64'
$portableNode = Join-Path $portableRoot 'node.exe'
$portableNpm = Join-Path $portableRoot 'npm.cmd'

if ($systemNode -and $systemNpm) {
  $nodePath = $systemNode.Path
  $npmPath = $systemNpm.Path
} elseif ((Test-Path $portableNode) -and (Test-Path $portableNpm)) {
  $nodePath = $portableNode
  $npmPath = $portableNpm
  $portableDir = Split-Path $portableNode -Parent
  $env:PATH = "$portableDir;$env:PATH"
} else {
  Write-Error "Node.js/npm are not available. Run .\install-node.ps1 first."
  exit 1
}

Write-Host "Using Node: $nodePath"
Write-Host "Using npm: $npmPath"

if (Test-Path "node_modules") {
  Write-Host "Removing existing node_modules to avoid stale install state..."
  Remove-Item "node_modules" -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Installing frontend dependencies..."
& $npmPath install
if ($LASTEXITCODE -ne 0) {
  Write-Error "npm install failed with exit code $LASTEXITCODE."
  exit $LASTEXITCODE
}

Write-Host "Starting Next.js frontend..."
Start-Process -FilePath $npmPath -ArgumentList 'run', 'dev' -NoNewWindow
Write-Host "Frontend started. Open http://localhost:3000 in your browser."
