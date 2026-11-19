<#
.SYNOPSIS
    Safe, reversible system debloat utility for Google Pixel 10 Pro.
.DESCRIPTION
    Supports listing installed packages, dry-run preview, user-0 uninstall
    (pm uninstall -k --user 0), and restoring previously removed packages
    (cmd package install-existing).
.EXAMPLE
    .\debloat-pixel.ps1 -Mode list
    .\debloat-pixel.ps1 -Mode dry-run
    .\debloat-pixel.ps1 -Mode debloat
    .\debloat-pixel.ps1 -Mode restore -Package com.google.android.apps.youtube.music
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("list", "dry-run", "debloat", "restore")]
    [string]$Mode,

    [string]$Target = "58311FDCH000CF",
    [string]$Package
)

$ErrorActionPreference = "Stop"
$AdbPath = "D:\DND\HomeAutomation\tools\platform-tools\adb.exe"
$LogFile = Join-Path $PSScriptRoot "debloat_history.log"
$PackagesDump = Join-Path $PSScriptRoot "installed_packages.txt"

function Resolve-PixelTarget {
    param([string]$PreferredTarget)
    $lines = & $AdbPath devices -l
    $pixelLine = $lines | Select-String -Pattern "model:Pixel_10_Pro|58311FDCH000CF" | Select-Object -First 1
    if ($pixelLine) {
        return ($pixelLine.ToString().Trim() -split "\s+")[0]
    }
    return $PreferredTarget
}

# Exact user-approved package removal list for Pixel 10 Pro.
$BloatCandidates = @(
    "com.android.chrome",                     # Chrome
    "com.google.android.youtube",             # YouTube
    "com.google.android.apps.youtube.music",  # YouTube Music
    "com.cleandroid.android_junk_cleaner",    # Junk Cleaner
    "com.mxtech.videoplayer.ad",              # MX Player
    "com.zeptoconsumerapp",                   # Zepto
    "in.swiggy.android",                      # Swiggy
    "com.grofers.customerapp"                 # Blinkit
)

$serial = Resolve-PixelTarget -PreferredTarget $Target

switch ($Mode) {
    "list" {
        Write-Host "Fetching installed packages from $serial..." -ForegroundColor Cyan
        $pkgs = & $AdbPath -s $serial shell pm list packages | ForEach-Object { $_ -replace "^package:", "" } | Sort-Object
        $pkgs | Set-Content -Path $PackagesDump -Encoding UTF8
        Write-Host "Saved $($pkgs.Count) packages to $PackagesDump" -ForegroundColor Green
    }

    "dry-run" {
        Write-Host "Dry-run on $serial. Checking which candidate packages are installed..." -ForegroundColor Cyan
        $installed = & $AdbPath -s $serial shell pm list packages | ForEach-Object { ($_ -replace "^package:", "").Trim() }
        foreach ($pkg in $BloatCandidates) {
            if ($installed -contains $pkg) {
                Write-Host "  [WOULD REMOVE] $pkg" -ForegroundColor Yellow
            } else {
                Write-Host "  [NOT PRESENT]  $pkg" -ForegroundColor DarkGray
            }
        }
    }

    "debloat" {
        $installed = & $AdbPath -s $serial shell pm list packages | ForEach-Object { ($_ -replace "^package:", "").Trim() }
        foreach ($pkg in $BloatCandidates) {
            if ($installed -contains $pkg) {
                Write-Host "Removing (user 0): $pkg" -ForegroundColor Yellow
                $res = (& $AdbPath -s $serial shell pm uninstall -k --user 0 $pkg) -join " "
                $actionType = "UNINSTALL"
                if ($res -match "only root can delete system app") {
                    $res = (& $AdbPath -s $serial shell pm disable-user --user 0 $pkg) -join " "
                    $actionType = "DISABLE"
                }
                $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                "$stamp | $actionType | $serial | $pkg | $res" | Add-Content -Path $LogFile -Encoding UTF8
                Write-Host "  -> $res"
            }
        }
        Write-Host "Debloat pass complete. History logged to $LogFile" -ForegroundColor Green
    }

    "restore" {
        if (-not $Package) {
            throw "Action 'restore' requires -Package <package.name>."
        }
        Write-Host "Restoring package $Package on $serial..." -ForegroundColor Cyan
        $res = (& $AdbPath -s $serial shell cmd package install-existing $Package) -join " "
        $null = & $AdbPath -s $serial shell pm enable $Package 2>$null
        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        "$stamp | RESTORE | $serial | $Package | $res" | Add-Content -Path $LogFile -Encoding UTF8
        Write-Host "  -> $res" -ForegroundColor Green
    }
}
