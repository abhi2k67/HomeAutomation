# 02 — Google Pixel 10 Pro (Android)

100% local LAN / USB workspace for debloating, minimalist pure-black launcher setup, wireless `scrcpy`, and two-way laptop-phone automation.

## 1. Connect Pixel 10 Pro
- **Via USB:** Plug in the Pixel 10 Pro with USB Debugging enabled, then verify:
  ```powershell
  .\adb-pixel.ps1 -Action status
  ```
- **Switch USB -> Wi-Fi ADB (port 5555):**
  ```powershell
  .\adb-pixel.ps1 -Action tcpip
  ```
- **Via Android Wireless Debugging (no USB):**
  On the Pixel: **Settings -> Developer options -> Wireless debugging -> Pair device with pairing code**, then:
  ```powershell
  .\adb-pixel.ps1 -Action pair -Ip <PIXEL_IP> -Port <PAIR_PORT> -Code <CODE> -ConnectPort <CONNECT_PORT>
  ```

## 2. System Debloat (Safe & Reversible)
1. Dump all currently installed packages to `installed_packages.txt`:
   ```powershell
   .\debloat-pixel.ps1 -Mode list
   ```
2. Preview what will be removed:
   ```powershell
   .\debloat-pixel.ps1 -Mode dry-run
   ```
3. Run the debloat pass (logs every action to `debloat_history.log`):
   ```powershell
   .\debloat-pixel.ps1 -Mode debloat
   ```
4. Restore any package if needed:
   ```powershell
   .\debloat-pixel.ps1 -Mode restore -Package <package.name>
   ```

## 3. Minimalist Pure-Black Launcher & Wireless `scrcpy`
- Install `scrcpy` locally if not present: `winget install Genymobile.scrcpy`, then run `.\adb-pixel.ps1 -Action scrcpy`.
- Minimalist pure-black (`#000000`) open-source launcher APK (e.g. **Olauncher** or **Minimo**) can be sideloaded locally once downloaded:
  ```powershell
  adb -s <PIXEL_TARGET> install path\to\launcher.apk
  ```

## 4. Phone -> Laptop Local HTTP Bridge
Run the zero-dependency local LAN server on the HP EliteBook:
```powershell
py .\laptop_bridge.py
```
Test from the Pixel (browser or HTTP Shortcuts app on the same Wi-Fi):
- `GET http://<LAPTOP_LAN_IP>:8765/health`
- `GET http://<LAPTOP_LAN_IP>:8765/devices`
- `POST http://<LAPTOP_LAN_IP>:8765/action` with `{"action": "ping"}`
