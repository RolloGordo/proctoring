param(
    [string]$Audio = '',
    [ValidateSet('base','small','tiny')][string]$Model = 'small',
    [switch]$Offline
)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Falta instalar el entorno. Revisa docs/SP-007-guide.md.'
}
if ($Audio) { $Audio = (Resolve-Path -LiteralPath $Audio).Path }
$extraArgs = @()
if ($Offline) { $extraArgs += '--offline' }
Push-Location $PSScriptRoot
try {
    if ($Audio) { $extraArgs += @('--audio', $Audio) }
    & $pythonPath -m spikes.demo --model $Model @extraArgs
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo completar la transcripción.' }
} finally { Pop-Location }
