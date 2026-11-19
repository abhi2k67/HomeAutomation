<#
.SYNOPSIS
    Instant Theme, Layout & Visual FX controller for Minimal Trio Launcher on Pixel 10 Pro.
.EXAMPLE
    .\switch-theme.ps1 -Theme chrono
    .\switch-theme.ps1 -Theme emerald
    .\switch-theme.ps1 -Theme obsidian -Layout classic
    .\switch-theme.ps1 -Theme cycle
    .\switch-theme.ps1 -Fx mono -SystemGrayscale on
#>
[CmdletBinding()]
param(
    [ValidateSet("chrono", "emerald", "obsidian", "1", "2", "3", "cycle")]
    [string]$Theme,

    [ValidateSet("signature", "classic", "text", "0", "1", "2")]
    [string]$Layout,

    [ValidateSet("120hz", "still", "mono", "0", "1", "2")]
    [string]$Fx,

    [ValidateSet("on", "off")]
    [string]$SystemGrayscale,

    [string]$Target = "58311FDCH000CF"
)

$ErrorActionPreference = "Stop"
$Adb = "D:\DND\HomeAutomation\tools\platform-tools\adb.exe"

$intentArgs = @("-n", "com.dnd.minimaltrio/.MainActivity")

if ($Theme) {
    $tVal = switch ($Theme.ToLower()) {
        "chrono"   { 1 }
        "1"        { 1 }
        "emerald"  { 2 }
        "2"        { 2 }
        "obsidian" { 3 }
        "3"        { 3 }
        "cycle"    { 0 }
    }
    $intentArgs += @("--ei", "theme", "$tVal")
}

if ($Layout) {
    $lVal = switch ($Layout.ToLower()) {
        "signature" { 0 }
        "0"         { 0 }
        "classic"   { 1 }
        "1"         { 1 }
        "text"      { 2 }
        "2"         { 2 }
    }
    $intentArgs += @("--ei", "layout", "$lVal")
}

if ($Fx) {
    $fVal = switch ($Fx.ToLower()) {
        "120hz" { 0 }
        "0"     { 0 }
        "still" { 1 }
        "1"     { 1 }
        "mono"  { 2 }
        "2"     { 2 }
    }
    $intentArgs += @("--ei", "fx", "$fVal")
}

if ($SystemGrayscale) {
    if ($SystemGrayscale -eq "on") {
        Write-Host "Enabling system-wide monochrome grayscale filter..." -ForegroundColor Cyan
        & $Adb -s $Target shell "settings put secure accessibility_display_daltonizer_enabled 1; settings put secure accessibility_display_daltonizer 0"
    } else {
        Write-Host "Restoring full system color..." -ForegroundColor Cyan
        & $Adb -s $Target shell "settings put secure accessibility_display_daltonizer_enabled 0"
    }
}

Write-Host "Applying theme settings to Pixel 10 Pro ($Target)..." -ForegroundColor Cyan
& $Adb -s $Target shell am start @intentArgs
