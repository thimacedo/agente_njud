param(
    [ValidateSet('setup','backend','test','pipeline','check')]
    [string]$Action = 'check'
)
$Rest = $args
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv_pipeline/Scripts/python.exe'
if ($Action -eq 'setup') {
    if (-not (Test-Path -LiteralPath $python)) {
        & py -3.11 -m venv (Join-Path $PSScriptRoot '.venv_pipeline')
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    & $python -c "import sys; assert sys.version_info[:2] == (3, 11), 'Use Python 3.11'"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -m pip install -r (Join-Path $PSScriptRoot 'requirements-dev.txt')
    exit $LASTEXITCODE
}
if (-not (Test-Path -LiteralPath $python)) { throw 'Execute ./dev.ps1 setup primeiro.' }
$oldPath = $env:PYTHONPATH
$oldTmp = $env:DIVISOR_TMP
Push-Location $PSScriptRoot
try {
    $env:PYTHONPATH = "$PSScriptRoot/scripts_pipeline;$PSScriptRoot" + $(if ($oldPath) { ";$oldPath" })
    if ($Action -in @('backend','pipeline') -and -not $env:DIVISOR_TMP) {
        $env:DIVISOR_TMP = Join-Path $PSScriptRoot 'data/tmp'
        New-Item -ItemType Directory -Force -Path $env:DIVISOR_TMP | Out-Null
    }
    switch ($Action) {
        'backend' { & $python (Join-Path $PSScriptRoot 'frontend/server.py') @Rest }
        'test' { & $python -m pytest @Rest }
        'pipeline' { & $python @Rest }
        'check' {
            & $python -m pip check
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $python -c "import sys,fastapi,pydub,pytest,uvicorn,multipart,httpx,httpx2,faster_whisper; print(sys.executable)"
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            foreach ($tool in @('ffmpeg','ffprobe')) { Get-Command $tool -ErrorAction Stop | Select-Object Name,Source }
        }
    }
    exit $LASTEXITCODE
} finally { $env:PYTHONPATH = $oldPath; $env:DIVISOR_TMP = $oldTmp; Pop-Location }
