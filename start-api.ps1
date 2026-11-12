$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    $python = $venvPython
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python was not found. Install Python 3.10 or newer and try again."
    }
    $python = $pythonCommand.Source
}

& $python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
