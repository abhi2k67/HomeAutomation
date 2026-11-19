param(
    [switch]$BuildOnly
)

$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$ToolsRoot   = "D:\DND\HomeAutomation\tools"
$SdkRoot     = "$ToolsRoot\android-sdk"
$BuildTools  = "$SdkRoot\build-tools\34.0.0"
$PlatformJar = "$SdkRoot\platforms\android-34\android.jar"
$Adb         = "$ToolsRoot\platform-tools\adb.exe"
$BuildDir    = "$ProjectRoot\build"

# Ensure Java 17 is on PATH
$Jdk = Get-ChildItem "C:\Program Files\Microsoft\jdk-17*" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if ($Jdk) {
    $env:JAVA_HOME = $Jdk
    $env:PATH = "$Jdk\bin;$env:PATH"
}

if (-not (Test-Path "$BuildTools\aapt2.exe")) {
    throw "Android build-tools 34.0.0 not found at $BuildTools"
}

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

Write-Host "[1/4] Compiling resources with aapt2..." -ForegroundColor Cyan
& "$BuildTools\aapt2.exe" compile --dir "$ProjectRoot\res" -o "$BuildDir\res.zip"
if ($LASTEXITCODE -ne 0) { throw "aapt2 compile failed" }

Write-Host "[2/4] Linking APK..." -ForegroundColor Cyan
& "$BuildTools\aapt2.exe" link `
    -o "$BuildDir\unsigned.apk" `
    -I $PlatformJar `
    --manifest "$ProjectRoot\AndroidManifest.xml" `
    "$BuildDir\res.zip"
if ($LASTEXITCODE -ne 0) { throw "aapt2 link failed" }

Write-Host "[3/4] Aligning & signing APK..." -ForegroundColor Cyan
& "$BuildTools\zipalign.exe" -p -f 4 "$BuildDir\unsigned.apk" "$BuildDir\aligned.apk"
if ($LASTEXITCODE -ne 0) { throw "zipalign failed" }

$Keystore = "$BuildDir\watchface.jks"
if (-not (Test-Path $Keystore)) {
    keytool -genkeypair -v `
        -keystore $Keystore `
        -storepass "watchface" `
        -keypass "watchface" `
        -alias "trio" `
        -keyalg RSA -keysize 2048 -validity 10000 `
        -dname "CN=MinimalTrio, OU=HomeAutomation, O=Local, C=IN" | Out-Null
}

$OutApk = "$BuildDir\MinimalTrio.apk"
& "$BuildTools\apksigner.bat" sign `
    --ks $Keystore `
    --ks-pass "pass:watchface" `
    --key-pass "pass:watchface" `
    --out $OutApk `
    "$BuildDir\aligned.apk"
if ($LASTEXITCODE -ne 0) { throw "apksigner failed" }

Write-Host "Built: $OutApk" -ForegroundColor Green

if ($BuildOnly) { exit 0 }

Write-Host "[4/4] Checking ADB for Xiaomi Watch 2 Pro..." -ForegroundColor Cyan
$Devices = & $Adb devices -l
$WatchLine = $Devices | Select-String "Xiaomi_Watch_2_Pro|_adb-tls-connect" | Select-Object -First 1

if (-not $WatchLine) {
    Write-Warning "Watch is not currently awake on Wi-Fi ADB. Wake the watch screen (or toggle Wireless debugging) and re-run this script, or run:"
    Write-Host "  `"$Adb`" install -r `"$OutApk`""
    exit 0
}

$WatchSerial = ($WatchLine.ToString().Trim() -split "\s+")[0]
Write-Host "Installing to $WatchSerial..." -ForegroundColor Cyan
& $Adb -s $WatchSerial install -r $OutApk
if ($LASTEXITCODE -ne 0) { throw "adb install failed" }

Write-Host "Installed! Long-press your watch face -> Add/Customize -> select 'Minimal Trio'." -ForegroundColor Green
