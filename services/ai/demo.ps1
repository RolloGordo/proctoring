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
    if (-not $Audio) {
        $sample = Import-Csv -LiteralPath 'datasets\mediaspeech_es\manifest.csv' | Select-Object -First 1
        $Audio = Join-Path 'datasets\mediaspeech_es' $sample.audio_path
        Write-Host 'Referencia del dataset:'
        Write-Host $sample.reference
        Write-Host ''
        $referencePath = [IO.Path]::ChangeExtension($Audio, '.txt')
        & $pythonPath -m spikes.transcribe $Audio --model $Model --reference $referencePath --output results/demo.json @extraArgs
    } else {
        & $pythonPath -m spikes.transcribe $Audio --model $Model --output results/demo.json @extraArgs
    }
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo completar la transcripción.' }
    Write-Host 'Esta demostración transcribe audio; no detecta fraude.'
} finally { Pop-Location }
