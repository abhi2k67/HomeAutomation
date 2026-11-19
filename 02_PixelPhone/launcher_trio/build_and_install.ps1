param(
    [switch]$BuildOnly,
    [string]$Target = "58311FDCH000CF"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$ToolsRoot   = "D:\DND\HomeAutomation\tools"
$SdkRoot     = "$ToolsRoot\android-sdk"
$BuildTools  = "$SdkRoot\build-tools\34.0.0"
$PlatformJar = "$SdkRoot\platforms\android-34\android.jar"
$Adb         = "$ToolsRoot\platform-tools\adb.exe"
$BuildDir    = "$ProjectRoot\build"
$GenJavaDir  = "$BuildDir\gen"
$ClassesDir  = "$BuildDir\classes"

# Locate JDK 17
$Jdk = Get-ChildItem "C:\Program Files\Microsoft\jdk-17*" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if (-not $Jdk) {
    throw "Microsoft JDK 17 not found under C:\Program Files\Microsoft\jdk-17*"
}
$env:JAVA_HOME = $Jdk
$env:PATH = "$Jdk\bin;$env:PATH"

if (Test-Path $BuildDir) {
    Remove-Item -Recurse -Force "$GenJavaDir", "$ClassesDir" -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $BuildDir, $GenJavaDir, $ClassesDir | Out-Null

Write-Host "[1/6] Compiling resources with aapt2..." -ForegroundColor Cyan
& "$BuildTools\aapt2.exe" compile --dir "$ProjectRoot\res" -o "$BuildDir\res.zip"
if ($LASTEXITCODE -ne 0) { throw "aapt2 compile failed" }

Write-Host "[2/6] Linking resources and generating R.java..." -ForegroundColor Cyan
& "$BuildTools\aapt2.exe" link `
    -o "$BuildDir\unsigned_res.apk" `
    -I $PlatformJar `
    --manifest "$ProjectRoot\AndroidManifest.xml" `
    --java $GenJavaDir `
    "$BuildDir\res.zip"
if ($LASTEXITCODE -ne 0) { throw "aapt2 link failed" }

Write-Host "[3/6] Compiling Java sources with javac..." -ForegroundColor Cyan
$JavaFiles = @(
    Get-ChildItem -Path "$ProjectRoot\src", $GenJavaDir -Recurse -Filter "*.java" | Select-Object -ExpandProperty FullName
)
& "$Jdk\bin\javac.exe" -source 11 -target 11 -encoding UTF-8 -cp $PlatformJar -d $ClassesDir @JavaFiles
if ($LASTEXITCODE -ne 0) { throw "javac compilation failed" }

Write-Host "[4/6] Converting bytecode to classes.dex with d8..." -ForegroundColor Cyan
$ClassFiles = @(
    Get-ChildItem -Path $ClassesDir -Recurse -Filter "*.class" | Select-Object -ExpandProperty FullName
)
& "$BuildTools\d8.bat" --lib $PlatformJar --min-api 29 --output $BuildDir @ClassFiles
if ($LASTEXITCODE -ne 0) { throw "d8 dexing failed" }

Write-Host "[5/6] Packaging, zipaligning & signing MinimalTrioLauncher.apk..." -ForegroundColor Cyan
Copy-Item -Force "$BuildDir\unsigned_res.apk" "$BuildDir\unaligned.zip"
Compress-Archive -Path "$BuildDir\classes.dex" -Update -DestinationPath "$BuildDir\unaligned.zip"
Move-Item -Force "$BuildDir\unaligned.zip" "$BuildDir\unsigned.apk"

& "$BuildTools\zipalign.exe" -p -f 4 "$BuildDir\unsigned.apk" "$BuildDir\aligned.apk"
if ($LASTEXITCODE -ne 0) { throw "zipalign failed" }

$Keystore = "$BuildDir\launcher.jks"
if (-not (Test-Path $Keystore)) {
    & "$Jdk\bin\keytool.exe" -genkeypair -v `
        -keystore $Keystore `
        -storepass "minimaltrio" `
        -keypass "minimaltrio" `
        -alias "trio" `
        -keyalg RSA -keysize 2048 -validity 10000 `
        -dname "CN=MinimalTrioLauncher, OU=HomeAutomation, O=Local, C=IN" | Out-Null
}

$OutApk = "$BuildDir\MinimalTrioLauncher.apk"
& "$BuildTools\apksigner.bat" sign `
    --ks $Keystore `
    --ks-pass "pass:minimaltrio" `
    --key-pass "pass:minimaltrio" `
    --out $OutApk `
    "$BuildDir\aligned.apk"
if ($LASTEXITCODE -ne 0) { throw "apksigner failed" }

Write-Host "Built APK: $OutApk" -ForegroundColor Green
if ($BuildOnly) { exit 0 }

Write-Host "[6/6] Installing MinimalTrioLauncher on Pixel 10 Pro ($Target)..." -ForegroundColor Cyan
& $Adb -s $Target install -r $OutApk
if ($LASTEXITCODE -ne 0) { throw "adb install failed" }

Write-Host "Pushing high-res wallpapers to /sdcard/Pictures/MinimalTrio/..." -ForegroundColor Cyan
& $Adb -s $Target shell "mkdir -p /sdcard/Pictures/MinimalTrio"
Get-ChildItem "$ProjectRoot\wallpapers\*.png" | ForEach-Object {
    & $Adb -s $Target push $_.FullName "/sdcard/Pictures/MinimalTrio/$($_.Name)" | Out-Null
}

Write-Host "Setting Minimal Trio as default HOME launcher, 24/7 Hardware Monochrome & 0.5x animations..." -ForegroundColor Cyan
& $Adb -s $Target shell "settings put global window_animation_scale 0.5; settings put global transition_animation_scale 0.5; settings put global animator_duration_scale 0.5; settings put secure accessibility_display_daltonizer_enabled 1; settings put secure accessibility_display_daltonizer 0; settings put secure lockscreen_use_double_line_clock 0; settings put secure doze_always_on 1; settings put secure lock_screen_show_notifications 0"
& $Adb -s $Target shell "cmd role add-role-holder android.app.role.HOME com.dnd.minimaltrio"
& $Adb -s $Target shell "am start -n com.dnd.minimaltrio/.MainActivity --es mode auto"

Write-Host "Done! Minimal Trio Launcher is now active on your Pixel 10 Pro." -ForegroundColor Green
