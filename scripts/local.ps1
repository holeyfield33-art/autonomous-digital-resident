param(
    [ValidateSet('start','stop','pause','resume','status','observe')][string]$Action = 'status',
    # Empty = the original resident (.resident\live, workspace\live, resident-sandbox).
    # A name runs a separate resident: .resident\<Name>\live, workspace\<Name>, resident-sandbox-<Name>.
    [ValidatePattern('^$|^[a-z0-9][a-z0-9-]{0,30}$')][string]$Name = '',
    [string]$Soul = '',
    [string]$MnemeConfig = '',
    [string]$ExecutionImage = '',
    [int]$Interval = 300,
    [int]$Steps = 12,
    [string]$BudgetUsd = '15',
    [switch]$Sandbox,
    [switch]$SandboxOffline,
    [switch]$NoWeb,
    [int]$Port = 8766
)
$ErrorActionPreference = 'Stop'
if ($Name -in @('live','demo')) { throw "-Name cannot be 'live' or 'demo'." }
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot '.venv\Scripts\python.exe'
if ($Name) {
    $privateRoot = Join-Path $repoRoot ".resident\$Name\live"
    $scope = @('--home',".resident/$Name",'--workspace',"workspace/$Name",'--sandbox-name',"resident-sandbox-$Name")
} else {
    $privateRoot = Join-Path $repoRoot '.resident\live'
    $scope = @()
}
$recordPath = Join-Path $privateRoot 'service.json'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Install the local .venv first; see README.' }
Push-Location $repoRoot
try {
    if ($Action -in @('stop','pause','resume','status')) {
        & $pythonPath -m agent.cli $Action --live @scope
        if ($LASTEXITCODE -ne 0) { throw "Resident $Action failed." }
        return
    }
    if ($Action -eq 'observe') {
        & $pythonPath -m agent.cli observe --live --port $Port @scope
        return
    }
    if ($Soul -and -not (Test-Path -LiteralPath $Soul -PathType Leaf)) { throw "Soul file not found: $Soul" }
    if ($Name -and -not $Soul) { throw 'A named resident needs -Soul so its identity is explicit.' }
    if (Test-Path -LiteralPath $recordPath) {
        $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        $existing = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
        if ($existing -and $existing.StartTime.ToUniversalTime().ToString('o') -eq $record.started_utc) {
            Write-Output 'Managed Resident process already exists; use status or resume.'
            return
        }
    }
    New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null
    & $pythonPath -m agent.cli resume --live @scope
    if ($LASTEXITCODE -ne 0) { throw 'Could not clear operator STOP/PAUSE markers.' }
    $arguments = @('-m','agent.cli','run','--live','--mneme','--cycles','0','--interval',"$Interval",'--steps',"$Steps",'--budget-usd',$BudgetUsd) + $scope
    if ($Soul) { $arguments += @('--soul',('"' + $Soul + '"')) }
    if ($Sandbox) { $arguments += '--sandbox' }
    if ($SandboxOffline) { $arguments += '--sandbox-offline' }
    if ($NoWeb) { $arguments += '--no-web' }
    if ($MnemeConfig) { $arguments += @('--mneme-config',('"' + $MnemeConfig + '"')) }
    if ($ExecutionImage) { $arguments += @('--execution-image',$ExecutionImage) }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $stdoutPath = Join-Path $privateRoot "resident-$stamp.stdout.log"
    $stderrPath = Join-Path $privateRoot "resident-$stamp.stderr.log"
    $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    @{pid=$process.Id;started_utc=$process.StartTime.ToUniversalTime().ToString('o');stdout=$stdoutPath;stderr=$stderrPath} | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding UTF8
    Write-Output "Resident $(if ($Name) { $Name } else { 'live' }) started under its durable cap. PID $($process.Id)."
    Write-Output "Activity: $stderrPath"
} finally { Pop-Location }
