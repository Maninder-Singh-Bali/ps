param([switch]$NoBrowser,[switch]$NoRenderer)
$ErrorActionPreference = 'Stop'
$studioRoot = $PSScriptRoot
$studioPython = Join-Path $studioRoot 'runtime\python\pythonw.exe'
$studioConfig = Get-Content -LiteralPath (Join-Path $studioRoot 'studio.local.json') -Raw | ConvertFrom-Json
$studioPort = [int]$studioConfig.dashboard_port
if ($studioPort -lt 1024 -or $studioPort -gt 65535) { throw 'Invalid dashboard_port in studio.local.json.' }
$studioUrl = "http://127.0.0.1:$studioPort"
$studioMutex = New-Object System.Threading.Mutex($false, "Local\PixeloidStudioLauncher$studioPort")
try {
if (-not $studioMutex.WaitOne(0)) { return }
$studioRunning = $false
try {
    $studioResponse = Invoke-RestMethod -Uri "$studioUrl/api/identity" -TimeoutSec 3
    $studioRunning = $studioResponse.app -eq 'Pixeloid Studio'
} catch {}
if (-not $studioRunning) {
    $studioSocket = New-Object System.Net.Sockets.TcpClient
    try { $studioSocket.Connect('127.0.0.1', $studioPort); $studioOccupied = $true } catch { $studioOccupied = $false } finally { $studioSocket.Dispose() }
    if ($studioOccupied) { throw 'The dashboard port is occupied. Nothing was stopped. Check studio.local.json.' }
    if (-not (Test-Path -LiteralPath $studioPython)) { throw 'The bundled runtime is missing. Restore the runtime folder from your Pixeloid Studio package.' }
    Start-Process -FilePath $studioPython -ArgumentList @('"' + (Join-Path $studioRoot 'server.py') + '"','--port',"$studioPort") -WorkingDirectory $studioRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $studioRoot 'app.log') -RedirectStandardError (Join-Path $studioRoot 'app-error.log')
    for ($studioAttempt=0; $studioAttempt -lt 30; $studioAttempt++) {
        Start-Sleep -Milliseconds 500
        try { $studioResponse = Invoke-RestMethod -Uri "$studioUrl/api/identity" -TimeoutSec 2; $studioRunning = $studioResponse.app -eq 'Pixeloid Studio'; if ($studioRunning) { break } } catch {}
    }
    if (-not $studioRunning) { throw 'Pixeloid Studio could not start. Read app-error.log in this folder.' }
}
if ($studioConfig.auto_start_renderer -and -not $NoRenderer) {
    try { $null = Invoke-RestMethod -Uri "$studioUrl/api/renderer/start" -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 35 } catch { Write-Warning 'Renderer needs attention. Open System check in the dashboard; your projects are still available.' }
}
if (-not $NoBrowser) { Start-Process $studioUrl }
Write-Output "Pixeloid Studio is ready at $studioUrl"
} finally {
    try { $studioMutex.ReleaseMutex() } catch {}
    $studioMutex.Dispose()
}
