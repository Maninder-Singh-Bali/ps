param([string]$InitialPath = '')
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Windows.Forms
$picker = New-Object System.Windows.Forms.FolderBrowserDialog
$picker.Description = 'Choose where Pixeloid Studio will create the project folder'
$picker.ShowNewFolderButton = $true
if ($InitialPath -and (Test-Path -LiteralPath $InitialPath -PathType Container)) { $picker.SelectedPath = $InitialPath }
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
try {
    $result = $picker.ShowDialog($owner)
    if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
        @{path=$picker.SelectedPath;cancelled=$false} | ConvertTo-Json -Compress
    } else { @{path='';cancelled=$true} | ConvertTo-Json -Compress }
} finally { $picker.Dispose(); $owner.Dispose() }
