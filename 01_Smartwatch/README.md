# Sub-Project 01: Xiaomi Watch 2 Pro (Wear OS)

100% local LAN / Wi-Fi ADB workflow for the Xiaomi Watch 2 Pro.

## 1. Local ADB (`platform-tools`)

- Binary location: `D:\DND\HomeAutomation\tools\platform-tools\adb.exe` (v37.0.1)
- Already registered in Windows User `PATH` (restart terminal/IDE if `adb` is not yet recognized in the current shell).

## 2. Wireless ADB Pairing (Xiaomi Watch 2 Pro)

1. On the watch, open **Settings > System > About** and tap **Build number** 7 times to enable **Developer options**.
2. Go to **Settings > Developer options**:
   - Enable **ADB debugging**.
   - Enable **Wireless debugging** (make sure the watch is on the same home Wi-Fi network as the EliteBook).
3. Tap **Wireless debugging > Pair new device** to display the **IP address & Port** and **6-digit pairing code**.
4. Run from PowerShell:
   ```powershell
   .\adb_watch.ps1 pair -Ip <WATCH_IP> -PairPort <PAIR_PORT> -Code <6_DIGIT_CODE>
   ```
5. Look at the main **Wireless debugging** screen on the watch for the **connection port** (different from the pairing port), then connect:
   ```powershell
   .\adb_watch.ps1 connect -Ip <WATCH_IP> -ConnectPort <CONNECT_PORT>
   ```
6. Verify telemetry:
   ```powershell
   .\adb_watch.ps1 status -Ip <WATCH_IP> -ConnectPort <CONNECT_PORT>
   ```

## 3. Watch Face Studio (Custom Photo Watch Faces)

Watch Face Studio (WFS) is not available via `winget` and is not currently installed on this machine.

1. Download the Windows 64-bit installer from the official Samsung Developer portal:
   https://developer.samsung.com/watch-face-studio/download.html
2. Install Watch Face Studio and place your project files and high-resolution personal photos inside `D:\DND\HomeAutomation\01_Smartwatch\watchfaces\`.
3. Once the watch is connected via Wireless ADB (`.\adb_watch.ps1 connect ...`), Watch Face Studio's **Run on Device** will detect the Xiaomi Watch 2 Pro over Wi-Fi ADB for direct local deployment (zero cloud).
