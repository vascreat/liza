param(
    [switch]$ForceRecreateVenv
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPath = Join-Path $ProjectRoot '.venv'
$RequirementsPath = Join-Path $ProjectRoot 'requirements.txt'
$EnvExamplePath = Join-Path $ProjectRoot 'env.exemple'
$EnvPath = Join-Path $ProjectRoot '.env'

function Write-Step {
    param([string]$Message)
    Write-Host "[setup] $Message"
}

function Get-PythonCommand {
    $candidates = @('py -3.13', 'py -3.12', 'py -3.11', 'py -3.10', 'py -3', 'python')
    foreach ($candidate in $candidates) {
        try {
            & cmd /c "$candidate --version" *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
        }
    }

    throw 'Python 3 was not found. Install Python 3.10+ and try again.'
}

if ($ForceRecreateVenv -and (Test-Path $VenvPath)) {
    Write-Step 'Removing existing virtual environment'
    Remove-Item -Recurse -Force $VenvPath
}

if (-not (Test-Path $VenvPath)) {
    $pythonCommand = Get-PythonCommand
    Write-Step "Creating virtual environment with $pythonCommand"
    & cmd /c "$pythonCommand -m venv \"$VenvPath\""
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to create virtual environment.'
    }
} else {
    Write-Step 'Using existing virtual environment'
}

$PythonExe = Join-Path $VenvPath 'Scripts\python.exe'
if (-not (Test-Path $PythonExe)) {
    throw 'Virtual environment Python executable was not found.'
}

Write-Step 'Upgrading pip'
& $PythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to upgrade pip.'
}

Write-Step 'Installing Python dependencies'
& $PythonExe -m pip install -r $RequirementsPath
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to install Python dependencies.'
}

if (-not (Test-Path $EnvPath)) {
    if (Test-Path $EnvExamplePath) {
        Write-Step 'Creating .env from env.exemple'
        Copy-Item $EnvExamplePath $EnvPath
    } else {
        Write-Step 'Skipping .env creation because env.exemple was not found'
    }
} else {
    Write-Step '.env already exists; leaving it unchanged'
}

Write-Step 'Setup complete'
Write-Host ''
Write-Host 'Next steps:'
Write-Host "1. Edit $EnvPath and fill in your Twitch credentials if needed."
Write-Host '2. Make sure Ollama is installed and your model already exists.'
Write-Host "3. Run the bot with: $PythonExe main.py"
