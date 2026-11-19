<#
.SYNOPSIS
    Pairs and connects to the Xiaomi Watch 2 Pro over local Wi-Fi ADB.
.EXAMPLE
    .\connect_watch.ps1
    .\connect_watch.ps1 -PairAddress "192.168.1.45:37123" -PairCode "123456" -ConnectAddress "192.168.1.45:41234"
#>
param(
    [string]$PairAddress,
    [string]$PairCode,
    [string]$ConnectAddress
)

$ErrorActionPreference = "Stop"

$LocalAdb = "D:\DND\HomeAutomation\tools\platform-tools\adb.exe"
if (Get-Command adb -ErrorAction SilentlyContinue) {
    $Adb = "adb"
} elseif (Test-Path $LocalAdb) {
    $Adb = $LocalAdb
} else {
    Write-Error "adb.exe not found in PATH or at $LocalAdb."
    exit 1
}

Write-Host "Using ADB: $Adb" -ForegroundColor Cyan

if (-not $PairAddress -and -not $ConnectAddress) {
    $doPair = Read-Host "Do you need to pair the watch for the first time? (y/N)"
    if ($doPair -match '^[yY]') {
        $PairAddress = Read-Host "Enter Pairing IP:Port (from watch 'Pair new device')"
        $PairCode = Read-Host "Enter 6-digit Wi-Fi pairing code"
    }
}

if ($PairAddress -and $PairCode) {
    Write-Host "Pairing with $PairAddress..." -ForegroundColor Yellow
    & $Adb pair $PairAddress $PairCode
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ADB pairing failed. Verify the watch and laptop are on the same Wi-Fi and the code hasn't expired."
        exit 1
    }
}

if (-not $ConnectAddress) {
    $ConnectAddress = Read-Host "Enter Wireless Debugging IP:Port (shown on main Wireless Debugging screen)"
}

Write-Host "Connecting to $ConnectAddress..." -ForegroundColor Yellow
& $Adb connect $ConnectAddress
if ($LASTEXITCODE -ne 0) {
    Write-Error "ADB connect failed."
    exit 1
}

Write-Host "`nConnected ADB devices:" -ForegroundColor Green
& $Adb devices -l

Write-Host "`nQuerying Xiaomi Watch 2 Pro status..." -ForegroundColor Cyan
$model = & $Adb -s $ConnectAddress shell getprop ro.product.model
$wearVer = & $Adb -s $ConnectAddress shell getprop ro.build.version.release
$battery = (& $Adb -s $ConnectAddress shell dumpsys battery | Select-String "level:").ToString().Trim()

Write-Host "  Model   : $model"
Write-Host "  Android : $wearVer"
Write-Host "  Battery : $battery"
