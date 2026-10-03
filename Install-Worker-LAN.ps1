param([Parameter(Mandatory=$true)][string]$Deployment,[Parameter(Mandatory=$true)][string]$Pythonw)
# Run once as Administrator. Does not touch RDP, existing Studio, or the renderer.
$ErrorActionPreference='Stop'
$Deployment=(Resolve-Path -LiteralPath $Deployment).Path
$Pythonw=(Resolve-Path -LiteralPath $Pythonw).Path
$config=Get-Content -LiteralPath (Join-Path $Deployment 'private/worker.local.json') -Raw | ConvertFrom-Json
try {
$rule='Pixeloid private TLS worker '+$config.port
if (-not (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue)) {
 New-NetFirewallRule -DisplayName $rule -Direction Inbound -Action Allow -Profile Private -Protocol TCP -LocalPort $config.port -LocalAddress $config.lan_ip -RemoteAddress $config.subnet -Program $Pythonw | Out-Null
}
$taskName='Pixeloid Studio - private GPU worker'
$action=New-ScheduledTaskAction -Execute $Pythonw -Argument ('"'+$Deployment+'\worker-release\run_worker.py" "'+$Deployment+'\private\worker.local.json"') -WorkingDirectory ($Deployment+'\worker-release')
$trigger=New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
if (-not (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) { Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null }
Write-Output 'Private-LAN rule and hidden logon task installed. No existing service restarted.'

@{success=$true;task=(Get-ScheduledTask -TaskName $taskName).State.ToString();rule=$rule} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Deployment 'private/installation-result.json')
} catch { @{success=$false;error=$_.ToString()} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Deployment 'private/installation-result.json'); throw }
