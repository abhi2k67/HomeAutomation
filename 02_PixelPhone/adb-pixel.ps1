<#
.SYNOPSIS
    Local ADB & wireless scrcpy helper for Google Pixel 10 Pro.
.DESCRIPTION
    100% local LAN/USB ADB utility to discover, pair, connect, inspect,
    and mirror/control the Pixel 10 Pro via scrcpy.
.EXAMPLE
    .\adb-pixel.ps1 -Action discover
    .\adb-pixel.ps1 -Action pair -Ip 192.168.0.25 -Port 37123 -Code 482910 -ConnectPort 41235
    .\adb-pixel.ps1 -Action tcpip
    .\adb-pixel.ps1 -Action status
    .\adb-pixel.ps1 -Action scrcpy
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("discover", "pair", "connect", "tcpip", "status", "scrcpy", "disconnect")]
    [string]$Action,

    [string]$Ip,
    [int]$Port = 5555,
    [string]$Code,
    [int]$ConnectPort,
    [string]$Target = "58311FDCH000CF"
)

$ErrorActionPreference = "Stop"
$AdbPath = "D:\DND\HomeAutomation\tools\platform-tools\adb.exe"

if (-not (Test-Path $AdbPath)) {
    throw "ADB executable not found at $AdbPath"
}

function Resolve-PixelTarget {
    param([string]$PreferredTarget)
    $lines = & $AdbPath devices -l
    $pixelLine = $lines | Select-String -Pattern "model:Pixel_10_Pro|58311FDCH000CF" | Select-Object -First 1
    if ($pixelLine) {
        return ($pixelLine.ToString().Trim() -split "\s+")[0]
    }
    return $PreferredTarget
}

switch ($Action) {
    "discover" {
        Write-Host "Scanning local network for ADB mDNS services..." -ForegroundColor Cyan
        & $AdbPath start-server | Out-Null
        & $AdbPath mdns services
        Write-Host "`nConnected ADB devices:" -ForegroundColor Cyan
        & $AdbPath devices -l
    }

    "pair" {
        if (-not $Ip -or -not $Port -or -not $Code) {
            throw "Action 'pair' requires -Ip, -Port, and -Code."
        }
        & $AdbPath pair "${Ip}:${Port}" $Code
        if ($ConnectPort) {
            & $AdbPath connect "${Ip}:${ConnectPort}"
        }
    }

    "connect" {
        if (-not $Ip) {
            throw "Action 'connect' requires -Ip (and optional -Port, default 5555)."
        }
        & $AdbPath connect "${Ip}:${Port}"
        & $AdbPath devices -l
    }

    "tcpip" {
        $serial = Resolve-PixelTarget -PreferredTarget $Target
        Write-Host "Switching $serial to Wi-Fi ADB on port $Port..." -ForegroundColor Cyan
        & $AdbPath -s $serial tcpip $Port
        $ipLine = & $AdbPath -s $serial shell ip -f inet addr show wlan0 | Select-String -Pattern "inet\s+(\d+\.\d+\.\d+\.\d+)" | Select-Object -First 1
        if ($ipLine -and $ipLine.Matches.Count -gt 0) {
            $phoneIp = $ipLine.Matches[0].Groups[1].Value
            Write-Host "Pixel Wi-Fi IP: $phoneIp" -ForegroundColor Green
            Write-Host "Unplug USB and run: .\adb-pixel.ps1 -Action connect -Ip $phoneIp -Port $Port" -ForegroundColor Yellow
        }
    }

    "disconnect" {
        if ($Ip) {
            & $AdbPath disconnect "${Ip}:${Port}"
        } else {
            & $AdbPath disconnect
        }
    }

    "status" {
        $serial = Resolve-PixelTarget -PreferredTarget $Target
        Write-Host "=== Pixel 10 Pro ($serial) ===" -ForegroundColor Cyan
        $model = & $AdbPath -s $serial shell getprop ro.product.model
        $androidVer = & $AdbPath -s $serial shell getprop ro.build.version.release
        $sdk = & $AdbPath -s $serial shell getprop ro.build.version.sdk
        Write-Host "Model   : $model"
        Write-Host "Android : $androidVer (SDK $sdk)"
        Write-Host "`n=== Battery ===" -ForegroundColor Cyan
        & $AdbPath -s $serial shell dumpsys battery |
            Select-String -Pattern "level:|scale:|status:|temperature:|AC powered:|USB powered:|Wireless powered:"
    }

    "scrcpy" {
        $scrcpyCmd = Get-Command scrcpy -ErrorAction SilentlyContinue
        if (-not $scrcpyCmd) {
            Write-Host "scrcpy is not installed or not on PATH." -ForegroundColor Yellow
            Write-Host "Install locally with: winget install Genymobile.scrcpy" -ForegroundColor Cyan
            return
        }
        $serial = Resolve-PixelTarget -PreferredTarget $Target
        Write-Host "Launching scrcpy for $serial..." -ForegroundColor Cyan
        & $scrcpyCmd.Source -s $serial --stay-awake --window-title "Pixel 10 Pro (Local)"
    }
}
