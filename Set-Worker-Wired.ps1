#requires -Version 7.2
[CmdletBinding(SupportsShouldProcess=$true)]
param([Parameter(Mandatory)][string]$Deployment,[Parameter(Mandatory)][string]$Python,
 [Parameter(Mandatory)][string]$Pythonw,[Parameter(Mandatory)][string]$InterfaceAlias,
 [Parameter(Mandatory)][string]$MacAddress)
# One-time/admin maintenance. Does not assign IPs or change internet routes.
$ErrorActionPreference='Stop'
$Deployment=(Resolve-Path -LiteralPath $Deployment).Path
$adapter=Get-NetAdapter -Name $InterfaceAlias -Physical
if ($adapter.Status -ne 'Up' -or $adapter.MediaType -ne '802.3') { throw 'Connect and verify a physical Ethernet adapter first; Wi-Fi is never modified.' }
$address=@(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '169.254.*' -and $_.AddressState -eq 'Preferred'})
if ($address.Count -ne 1) { throw 'Expected one working IPv4 address on the selected Ethernet interface.' }
$ip=$address[0].IPAddress; $prefix=$address[0].PrefixLength
if ($ip -notmatch '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)') { throw 'Worker requires an RFC1918 private address.' }
$pcBytes=[Net.IPAddress]::Parse($ip).GetAddressBytes();$macBytes=[Net.IPAddress]::Parse($MacAddress).GetAddressBytes()
if ($macBytes.Length -ne 4 -or $MacAddress -eq $ip) { throw 'Provide the Mac Ethernet IPv4 address.' }
$network=[byte[]]::new(4)
for($i=0;$i -lt 4;$i++) {
 $bits=[Math]::Min(8,[Math]::Max(0,$prefix-$i*8));$mask=if($bits -eq 0){0}else{(255 -shl (8-$bits)) -band 255}
 $network[$i]=$pcBytes[$i] -band $mask
 if (($macBytes[$i] -band $mask) -ne $network[$i]) { throw 'Mac Ethernet address must be on the same wired subnet.' }
}
$private=Join-Path $Deployment 'private';$pair=Join-Path $Deployment 'private-pairing'
$configPath=Join-Path $private 'worker.local.json';$c=Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
Write-Output "Proposed: HTTPS ${ip}:$($c.port), interface $InterfaceAlias, permitted peer $MacAddress. Internet routes unchanged."
if (-not $PSCmdlet.ShouldProcess('Idle Pixeloid worker only','Rebind to wired interface and rotate its pinned certificate')) {return}
& $Python (Join-Path $PSScriptRoot 'worker_admin.py') maintenance --config (Join-Path $pair 'remote.local.json')
if ($LASTEXITCODE -ne 0) {throw 'Worker maintenance check failed; nothing rebound.'}
$pidFile=Join-Path $private 'worker.pid';$workerPid=[int](Get-Content -LiteralPath $pidFile)
$process=Get-CimInstance Win32_Process -Filter "ProcessId=$workerPid"
if ($process.ExecutablePath -ne (Resolve-Path -LiteralPath $Pythonw).Path -or $process.CommandLine -notlike '*worker-release*run_worker.py*') {throw 'Worker ownership check failed.'}
$backup=Join-Path $private ('network-backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss'));New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $configPath -Destination $backup;Copy-Item -LiteralPath $c.certificate -Destination $backup;Copy-Item -LiteralPath $c.private_key -Destination $backup
Copy-Item -LiteralPath (Join-Path $pair 'remote.local.json') -Destination (Join-Path $backup 'remote.local.json')
$rsa=[Security.Cryptography.RSA]::Create(3072)
$request=[Security.Cryptography.X509Certificates.CertificateRequest]::new('CN=Pixeloid Private Wired Worker',$rsa,[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)
$san=[Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new();$san.AddIpAddress([Net.IPAddress]::Parse($ip));$request.CertificateExtensions.Add($san.Build())
$request.CertificateExtensions.Add([Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($true,$false,0,$true))
$certificate=$request.CreateSelfSigned([DateTimeOffset]::Now.AddMinutes(-5),[DateTimeOffset]::Now.AddYears(1))
$newCert=Join-Path $private 'worker-wired.pem';$newKey=Join-Path $private 'worker-wired.key'
[IO.File]::WriteAllText($newCert,$certificate.ExportCertificatePem());[IO.File]::WriteAllText($newKey,$rsa.ExportPkcs8PrivateKeyPem())
# Windows strong-host binding plus interface/peer-scoped firewall. No wildcard listen.
Set-NetConnectionProfile -InterfaceIndex $adapter.ifIndex -NetworkCategory Private
$rule='Pixeloid private wired TLS worker '+$c.port
Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $rule -Direction Inbound -Action Allow -Profile Private -InterfaceAlias $InterfaceAlias -Protocol TCP -LocalPort $c.port -LocalAddress $ip -RemoteAddress $MacAddress -Program $Pythonw | Out-Null
Stop-Process -Id $workerPid
$c.lan_ip=$ip;$c.subnet=([Net.IPAddress]::new($network)).ToString()+"/$prefix";$c.certificate=$newCert;$c.private_key=$newKey
$c | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
Copy-Item -LiteralPath $newCert -Destination (Join-Path $pair 'worker.pem')
@{url="https://${ip}:$($c.port)";certificate='worker.pem';token_file='worker.token'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $pair 'remote.local.json') -Encoding utf8
Start-Process -FilePath $Pythonw -ArgumentList @((Join-Path $Deployment 'worker-release/run_worker.py'),$configPath) -WorkingDirectory (Join-Path $Deployment 'worker-release') -WindowStyle Hidden
Get-NetFirewallRule -DisplayName ('Pixeloid private TLS worker '+$c.port) -ErrorAction SilentlyContinue | Disable-NetFirewallRule
Write-Output 'Worker rebound; queue remains in maintenance. Transfer the updated public certificate and remote.local.json to the Mac. Run worker_admin.py status, then resume after verification. Backup retained; existing dashboard and RDP were not changed.'
