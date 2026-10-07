param(
    [ValidateSet('start','stop','pause','resume','status','observe')][string]$Action = 'status',
    [string]$MnemeConfig = '',
    [string]$ExecutionImage = '',
    [int]$Interval = 300,
    [int]$Port = 8766
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot '.venv\Scripts\python.exe'
$privateRoot = Join-Path $repoRoot '.resident\live'
$recordPath = Join-Path $privateRoot 'service.json'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Install the local .venv first; see README.' }
Push-Location $repoRoot
try {
    if ($Action -in @('stop','pause','resume','status')) {
        & $pythonPath -m agent.cli $Action --live
        if ($LASTEXITCODE -ne 0) { throw "Resident $Action failed." }
        return
    }
    if ($Action -eq 'observe') {
        & $pythonPath -m agent.cli observe --live --port $Port
        return
    }
    if (Test-Path -LiteralPath $recordPath) {
        $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        $existing = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
        if ($existing -and $existing.StartTime.ToUniversalTime().ToString('o') -eq $record.started_utc) {
            Write-Output 'Managed Resident process already exists; use status or resume.'
            return
        }
    }
    & $pythonPath -m agent.cli resume --live
    if ($LASTEXITCODE -ne 0) { throw 'Could not clear operator STOP/PAUSE markers.' }
    $arguments = @('-m','agent.cli','run','--live','--mneme','--cycles','0','--interval',"$Interval")
    if ($MnemeConfig) { $arguments += @('--mneme-config',('"' + $MnemeConfig + '"')) }
    if ($ExecutionImage) { $arguments += @('--execution-image',$ExecutionImage) }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $stdoutPath = Join-Path $privateRoot "resident-$stamp.stdout.log"
    $stderrPath = Join-Path $privateRoot "resident-$stamp.stderr.log"
    $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    @{pid=$process.Id;started_utc=$process.StartTime.ToUniversalTime().ToString('o');stdout=$stdoutPath;stderr=$stderrPath} | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding UTF8
    Write-Output "Resident started under its durable cap. PID $($process.Id)."
    Write-Output "Activity: $stderrPath"
} finally { Pop-Location }
