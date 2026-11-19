<#
.SYNOPSIS
    Local Wireless ADB helper for Xiaomi Watch 2 Pro (Wear OS).
.DESCRIPTION
    Pairs, connects, and queries basic local telemetry over home Wi-Fi using
    the local Android platform-tools (adb.exe) without any cloud relays.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("pair", "connect", "status", "devices", "disconnect")]
    [string]$Action = "devices",

    [string]$Ip,
    [int]$PairPort,
    [string]$Code,
    [int]$ConnectPort
)

$ErrorActionPreference = "Stop"

$LocalAdb = "D:\DND\HomeAutomation\tools\platform-tools\adb.exe"
if (Test-Path $LocalAdb) {
    $Adb = $LocalAdb
} elseif (Get-Command adb -ErrorAction SilentlyContinue) {
    $Adb = "adb"
} else {
    throw "adb.exe not found at $LocalAdb or on PATH."
}

function Invoke-Adb {
    param([string[]]$AdbArgs)
    & $Adb @AdbArgs
}

switch ($Action) {
    "pair" {
        if (-not $Ip) { $Ip = Read-Host "Watch IP address (e.g. 192.168.1.50)" }
        if (-not $PairPort) { $PairPort = [int](Read-Host "Pairing Port shown on watch") }
        if (-not $Code) { $Code = Read-Host "6-digit Wi-Fi pairing code" }

        Write-Host "Pairing with ${Ip}:${PairPort}..." -ForegroundColor Cyan
        Invoke-Adb @("pair", "${Ip}:${PairPort}", $Code)
    }

    "connect" {
        if (-not $Ip) { $Ip = Read-Host "Watch IP address (e.g. 192.168.1.50)" }
        if (-not $ConnectPort) { $ConnectPort = [int](Read-Host "Wireless debugging Port (shown on main Wireless debugging screen)") }

        Write-Host "Connecting to ${Ip}:${ConnectPort}..." -ForegroundColor Cyan
        Invoke-Adb @("connect", "${Ip}:${ConnectPort}")
        Invoke-Adb @("devices", "-l")
    }

    "status" {
        $target = if ($Ip -and $ConnectPort) { "${Ip}:${ConnectPort}" } else { $null }
        $prefix = if ($target) { @("-s", $target) } else { @() }

        $model = (Invoke-Adb ($prefix + @("shell", "getprop", "ro.product.model"))) | Out-String
        $ver   = (Invoke-Adb ($prefix + @("shell", "getprop", "ro.build.version.release"))) | Out-String
        $bat   = (Invoke-Adb ($prefix + @("shell", "dumpsys", "battery"))) | Out-String

        $level = ([regex]::Match($bat, "level:\s*(\d+)")).Groups[1].Value
        $temp  = ([regex]::Match($bat, "temperature:\s*(\d+)")).Groups[1].Value
        $ac    = ([regex]::Match($bat, "AC powered:\s*(\w+)")).Groups[1].Value
        $usb   = ([regex]::Match($bat, "USB powered:\s*(\w+)")).Groups[1].Value
        $wl    = ([regex]::Match($bat, "Wireless powered:\s*(\w+)")).Groups[1].Value

        $tempC = if ($temp) { [math]::Round(([int]$temp) / 10.0, 1) } else { "N/A" }
        $charging = ($ac -eq "true" -or $usb -eq "true" -or $wl -eq "true")

        Write-Host "=== Watch Telemetry ===" -ForegroundColor Green
        Write-Host "Model     : $($model.Trim())"
        Write-Host "Wear/OS   : $($ver.Trim())"
        Write-Host "Battery   : ${level}% (Charging: $charging, Temp: ${tempC} C)"
    }

    "devices" {
        Invoke-Adb @("devices", "-l")
    }

    "disconnect" {
        if ($Ip -and $ConnectPort) {
            Invoke-Adb @("disconnect", "${Ip}:${ConnectPort}")
        } else {
            Invoke-Adb @("disconnect")
        }
    }
}
