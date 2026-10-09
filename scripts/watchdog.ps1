<#
  Resident watchdog: protects the host while the residents run.

  Two jobs, scoped ONLY to the resident agents (never touches mneme / surfacetrace /
  core / their volumes):
    1. Host disk guard - if the drive holding Docker + workspaces drops below
       -MinFreeGB, pause the resident agents (touch their PAUSE markers) and alert.
    2. Going-live guard - watch each resident sandbox for tunnel / reverse-proxy
       processes (ssh, ngrok, cloudflared, ...) that would expose a service to the
       public internet, and alert (and kill, with -KillTunnels).

  Prints one line per event to stdout (UTC, LEVEL, detail); silence means healthy.
  Designed to be streamed by a monitor or run from Task Scheduler (-Once).
#>
param(
    [int]$MinFreeGB = 6,
    [string]$Drive = 'C',
    [string[]]$Sandboxes = @('resident-sandbox', 'resident-sandbox-b', 'resident-sandbox-c', 'resident-sandbox-d'),
    [string[]]$StateDirs = @('.resident/live', '.resident/b/live', '.resident/c/live', '.resident/d/live'),
    [int]$IntervalSec = 120,
    [switch]$Once,
    [switch]$KillTunnels
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
# Tunnel / reverse-proxy / exposure tools the residents must not run (gate is operator-only going-live).
$pattern = 'ssh |sshd|ngrok|cloudflared|localtunnel|telebit|frpc|chisel|serveo|pagekite|localhost\.run|\bbore\b'

function Emit($level, $msg) {
    Write-Output ("{0} {1} {2}" -f (Get-Date).ToUniversalTime().ToString('o'), $level, $msg)
}

function Scan {
    # 1. Host disk
    $d = Get-CimInstance Win32_LogicalDisk -Filter ("DeviceID='{0}:'" -f $Drive)
    $freeGB = [math]::Round($d.FreeSpace / 1GB, 1)
    if ($freeGB -lt $MinFreeGB) {
        foreach ($s in $StateDirs) {
            $p = Join-Path $repo $s
            if (Test-Path -LiteralPath $p) { New-Item -ItemType File -Force -Path (Join-Path $p 'PAUSE') | Out-Null }
        }
        Emit 'DISK_CRITICAL' ("{0}: {1}GB free < {2}GB - paused resident agents (resume to clear)" -f $Drive, $freeGB, $MinFreeGB)
    }

    # 2. Tunnels inside the resident sandboxes only
    foreach ($c in $Sandboxes) {
        $running = (& docker inspect -f '{{.State.Running}}' $c 2>$null)
        if ($running -ne 'true') { continue }
        $ps = (& docker exec $c sh -c 'ps -eo pid,args 2>/dev/null') 2>$null
        $hits = $ps | Select-String -Pattern $pattern
        if ($hits) {
            if ($KillTunnels) { & docker exec $c sh -c ("pkill -9 -f '{0}' 2>/dev/null; true" -f $pattern) 2>$null | Out-Null }
            foreach ($h in $hits) {
                Emit ($(if ($KillTunnels) { 'TUNNEL_KILLED' } else { 'TUNNEL_SEEN' })) ("{0}: {1}" -f $c, $h.ToString().Trim())
            }
        }
    }
}

if ($Once) { Scan; return }
Emit 'WATCHDOG_UP' ("drive={0}: min_free={1}GB interval={2}s kill={3} sandboxes={4}" -f $Drive, $MinFreeGB, $IntervalSec, [bool]$KillTunnels, ($Sandboxes -join ','))
while ($true) {
    try { Scan } catch { Emit 'WATCHDOG_ERR' $_.Exception.Message }
    Start-Sleep -Seconds $IntervalSec
}
