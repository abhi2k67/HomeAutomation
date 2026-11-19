<#
.SYNOPSIS
    Local Wi-Fi ADB helper for Xiaomi Watch 2 Pro (Wear OS).
.DESCRIPTION
    100% local LAN/Wi-Fi ADB utility to discover, pair, connect, and query
    telemetry on the Xiaomi Watch 2 Pro without any cloud services.
.EXAMPLE
    .\adb-watch.ps1 -Action discover
    .\adb-watch.ps1 -Action pair -Ip 192.168.1.50 -Port 37123 -Code 482910 -ConnectPort 41235
    .\adb-watch.ps1 -Action connect -Ip 192.168.1.50 -Port 41235
    .\adb-watch.ps1 -Action status -Target 192.168.1.50:41235
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("discover", "pair", "connect", "status", "disconnect")]
    [string]$Action,

    [string]$Ip,
    [int]$Port,
    [string]$Code,
    [int]$ConnectPort,
    [string]$Target
)

$ErrorActionPreference = "Stop"
$AdbPath = "D:\DND\HomeAutomation\tools\platform-tools\adb.exe"

if (-not (Test-Path $AdbPath)) {
    throw "ADB executable not found at $AdbPath"
}

function Invoke-Adb {
    param([string[]]$Arguments)
    & $AdbPath @Arguments
}

switch ($Action) {
    "discover" {
        Write-Host "Scanning local network for ADB mDNS services..." -ForegroundColor Cyan
        Invoke-Adb @("start-server") | Out-Null
        Invoke-Adb @("mdns", "services")
        Write-Host "`nConnected ADB devices:" -ForegroundColor Cyan
        Invoke-Adb @("devices", "-l")
    }

    "pair" {
        if (-not $Ip -or -not $Port -or -not $Code) {
            throw "Action 'pair' requires -Ip, -Port, and -Code."
        }
        $pairEndpoint = "${Ip}:${Port}"
        Write-Host "Pairing with $pairEndpoint..." -ForegroundColor Cyan
        Invoke-Adb @("pair", $pairEndpoint, $Code)

        if ($ConnectPort) {
            $connectEndpoint = "${Ip}:${ConnectPort}"
            Write-Host "Connecting to $connectEndpoint..." -ForegroundColor Cyan
            Invoke-Adb @("connect", $connectEndpoint)
        } else {
            Write-Host "Paired. Run '.\adb-watch.ps1 -Action connect -Ip $Ip -Port <WirelessDebuggingPort>' to connect." -ForegroundColor Yellow
        }
    }

    "connect" {
        $endpoint = if ($Target) { $Target } elseif ($Ip -and $Port) { "${Ip}:${Port}" } else { throw "Provide -Target <ip:port> or both -Ip and -Port." }
        Write-Host "Connecting to $endpoint..." -ForegroundColor Cyan
        Invoke-Adb @("connect", $endpoint)
        Invoke-Adb @("devices", "-l")
    }

    "disconnect" {
        if ($Target) {
            Invoke-Adb @("disconnect", $Target)
        } elseif ($Ip -and $Port) {
            Invoke-Adb @("disconnect", "${Ip}:${Port}")
        } else {
            Invoke-Adb @("disconnect")
        }
    }

    "status" {
        $adbArgs = @()
        if ($Target) {
            $adbArgs += @("-s", $Target)
        } elseif ($Ip -and $Port) {
            $adbArgs += @("-s", "${Ip}:${Port}")
        }

        Write-Host "=== Device Info ===" -ForegroundColor Cyan
        $model = (Invoke-Adb ($adbArgs + @("shell", "getprop", "ro.product.model")))
        $androidVer = (Invoke-Adb ($adbArgs + @("shell", "getprop", "ro.build.version.release")))
        Write-Host "Model   : $model"
        Write-Host "Android : $androidVer"

        Write-Host "`n=== Battery ===" -ForegroundColor Cyan
        Invoke-Adb ($adbArgs + @("shell", "dumpsys", "battery")) |
            Select-String -Pattern "level:|scale:|status:|temperature:|AC powered:|USB powered:|Wireless powered:"

        Write-Host "`n=== Step / Fitness Services (if available) ===" -ForegroundColor Cyan
        Invoke-Adb ($adbArgs + @("shell", "dumpsys", "sensorservice")) |
            Select-String -Pattern "Step Counter|step" -CaseSensitive:$false |
            Select-Object -First 10
    }
}
