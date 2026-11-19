package com.dnd.minimaltrio;

import android.app.WallpaperManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.LauncherActivityInfo;
import android.content.pm.LauncherApps;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Process;
import android.os.SystemClock;
import android.os.UserHandle;
import android.os.UserManager;
import android.view.DisplayCutout;
import android.view.HapticFeedbackConstants;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Toast;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

public class LauncherView extends View {

    private static final String PREFS_NAME = "minimal_trio_prefs";
    private static final String KEY_LAYOUT = "layout_mode";
    private static final String KEY_FAVS = "favorite_packages";
    private static final String KEY_UNLOCK_DAY = "unlock_day_of_year";
    private static final String KEY_UNLOCK_COUNT = "unlock_count_today";

    // Bottom 5-Tool Dock selected by user (A3): PhonePe, Gmail, WhatsApp, Brave, Maps
    private static final String[] DOCK_PACKAGES = new String[]{
            "com.phonepe.app",
            "com.google.android.gm",
            "com.whatsapp",
            "com.brave.browser",
            "com.google.android.apps.maps"
    };

    private static final String[] DOCK_LABELS = new String[]{
            "PhonePe",
            "Gmail",
            "WhatsApp",
            "Brave",
            "Maps"
    };

    // Default 3D Drum Favorites (above the dock)
    private static final String[] DEFAULT_FAVORITES = new String[]{
            "com.google.android.dialer",
            "com.google.android.apps.messaging",
            "com.google.android.GoogleCamera",
            "com.google.android.apps.photos",
            "com.google.android.deskclock",
            "com.google.android.calendar",
            "com.azure.authenticator",
            "com.android.settings"
    };

    private static final String RAIL_CHARS = "☆ABCDEFGHIJKLMNOPQRSTUVWXYZ○◈";

    public static class AppEntry {
        public final String label;
        public final String packageName;
        public final String activityName;
        public final int iconKind;
        public final ComponentName componentName;
        public final UserHandle userHandle;
        public final boolean isPrivateSpace;
        public final boolean isActionRow;

        public AppEntry(String label, String packageName, String activityName, int iconKind,
                        ComponentName componentName, UserHandle userHandle,
                        boolean isPrivateSpace, boolean isActionRow) {
            this.label = label;
            this.packageName = packageName;
            this.activityName = activityName;
            this.iconKind = iconKind;
            this.componentName = componentName;
            this.userHandle = userHandle;
            this.isPrivateSpace = isPrivateSpace;
            this.isActionRow = isActionRow;
        }
    }

    private final SharedPreferences prefs;
    private final List<AppEntry> allApps = new ArrayList<>();
    private final List<AppEntry> privateApps = new ArrayList<>();
    private final List<AppEntry> visibleApps = new ArrayList<>();
    private final Set<String> favoritePackages = new HashSet<>();
    private UserHandle privateProfileHandle = null;

    private int layoutMode = 0; // 0 = 3D Drum + Icons, 2 = 3D Drum Pure Text
    private String dayNightOverride = "auto"; // "auto", "day", "night"
    private Boolean lastSyncedIsDay = null;

    // Daily unlock counter for Innovation 1 (Usage Pulse Horizon Oscilloscope)
    private int dailyUnlockCount = 1;

    // Innovation 5: 3-Second Intention Gate for non-essential apps
    private AppEntry pendingGateApp = null;
    private long gateStartMs = 0L;
    private static final long GATE_DURATION_MS = 3000L;
    private final RectF gateAbortRect = new RectF();

    // Lock Screen Magic (A1): Live Horological Astrolabe Wake Overlay
    private boolean wakeOverlayActive = false;
    private final RectF wakeUnlockRect = new RectF();

    private char activeFilterChar = '☆';
    private boolean isScrubbingRail = false;
    private float scrubY = -1f;
    private int lastScrubIndex = -1;

    private float scrollOffsetY = 0f;
    private float maxScrollY = 0f;
    private float touchStartX = 0f;
    private float touchStartY = 0f;
    private float lastTouchY = 0f;
    private boolean isDraggingList = false;
    private boolean longPressTriggered = false;
    private int pressedAppIndex = -1;
    private int pressedDockIndex = -1;
    private long lastCoreTapMs = 0L;

    private String bannerMessage = null;
    private long bannerUntilMs = 0L;

    private Bitmap nightSysWall;
    private Bitmap daySysWall;
    private Bitmap dayLockWall;
    private Bitmap nightLockWall;

    private final Paint uiPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint iconPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint subTextPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint monoPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint clockPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dialTickPaint = new Paint(Paint.ANTI_ALIAS_FLAG);

    private final RectF gaugeDeviceRect = new RectF();
    private final RectF quantumCardRect = new RectF();
    private final RectF quantumHeaderRect = new RectF();
    private final RectF[] dockSlotRects = new RectF[5];
    private final List<RectF> appRowRects = new ArrayList<>();

    private final float density;
    private final float scaledDensity;

    private long lastNetCheckMs = 0L;
    private boolean hasWifi = false;
    private boolean hasCellular = false;

    private final Runnable longPressRunnable = new Runnable() {
        @Override
        public void run() {
            if (!isDraggingList && !isScrubbingRail && pressedAppIndex >= 0 && pressedAppIndex < visibleApps.size()) {
                longPressTriggered = true;
                toggleFavorite(visibleApps.get(pressedAppIndex));
            }
        }
    };

    public LauncherView(Context context) {
        super(context);
        density = context.getResources().getDisplayMetrics().density;
        scaledDensity = context.getResources().getDisplayMetrics().scaledDensity;

        for (int i = 0; i < 5; i++) {
            dockSlotRects[i] = new RectF();
        }

        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        layoutMode = prefs.getInt(KEY_LAYOUT, 0) % 3;

        Set<String> savedFavs = prefs.getStringSet(KEY_FAVS, null);
        if (savedFavs == null || savedFavs.isEmpty()) {
            Collections.addAll(favoritePackages, DEFAULT_FAVORITES);
            saveFavorites();
        } else {
            favoritePackages.addAll(savedFavs);
        }

        incrementOrLoadUnlockCount(false);
        initPaints();
        loadWallpapers();
        reloadInstalledApps();
    }

    private float dp(float v) {
        return v * density;
    }

    private float sp(float v) {
        return v * scaledDensity;
    }

    private void initPaints() {
        iconPaint.setStyle(Paint.Style.STROKE);
        iconPaint.setStrokeWidth(dp(1.6f));
        iconPaint.setStrokeCap(Paint.Cap.ROUND);
        iconPaint.setStrokeJoin(Paint.Join.ROUND);

        textPaint.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        subTextPaint.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        monoPaint.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.NORMAL));
        clockPaint.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.BOLD));

        dialTickPaint.setStyle(Paint.Style.STROKE);
    }

    private void loadWallpapers() {
        try {
            nightSysWall = BitmapFactory.decodeResource(getResources(), R.drawable.wall_chrono);
            daySysWall = BitmapFactory.decodeResource(getResources(), R.drawable.wall_emerald);
            dayLockWall = BitmapFactory.decodeResource(getResources(), R.drawable.wall_obsidian);
            nightLockWall = BitmapFactory.decodeResource(getResources(), R.drawable.wall_lockscreen);
        } catch (Throwable ignored) {
        }
    }

    private void incrementOrLoadUnlockCount(boolean increment) {
        Calendar cal = Calendar.getInstance();
        int doy = cal.get(Calendar.DAY_OF_YEAR);
        int savedDoy = prefs.getInt(KEY_UNLOCK_DAY, -1);
        if (savedDoy != doy) {
            dailyUnlockCount = 1;
            prefs.edit().putInt(KEY_UNLOCK_DAY, doy).putInt(KEY_UNLOCK_COUNT, 1).apply();
        } else {
            dailyUnlockCount = prefs.getInt(KEY_UNLOCK_COUNT, 1);
            if (increment) {
                dailyUnlockCount++;
                prefs.edit().putInt(KEY_UNLOCK_COUNT, dailyUnlockCount).apply();
            }
        }
    }

    public void onScreenTurnedOff() {
        pendingGateApp = null;
        wakeOverlayActive = true;
        invalidate();
    }

    public void onScreenWoke() {
        incrementOrLoadUnlockCount(true);
        wakeOverlayActive = true;
        invalidate();
    }

    public void setWakeOverlayActive(boolean active) {
        wakeOverlayActive = active;
        invalidate();
    }

    public boolean cancelActiveGateOrOverlay() {
        if (pendingGateApp != null) {
            pendingGateApp = null;
            showBanner("LAUNCH ABORTED");
            invalidate();
            return true;
        }
        if (wakeOverlayActive) {
            wakeOverlayActive = false;
            invalidate();
            return true;
        }
        return false;
    }

    public void setDayNightOverride(String mode) {
        if (mode == null) return;
        String m = mode.toLowerCase(Locale.US).trim();
        if ("day".equals(m) || "night".equals(m) || "auto".equals(m)) {
            dayNightOverride = m;
            lastSyncedIsDay = null;
            showBanner("PALETTE // " + m.toUpperCase(Locale.US));
            invalidate();
        }
    }

    public void onHostResume() {
        reloadInstalledApps();
        refreshNetworkState(true);
        invalidate();
    }

    public boolean isFiltered() {
        return activeFilterChar != '☆';
    }

    public void resetToFavorites() {
        activeFilterChar = '☆';
        scrollOffsetY = 0f;
        rebuildVisibleApps();
        invalidate();
    }

    public void setLayoutMode(int mode) {
        layoutMode = ((mode % 3) + 3) % 3;
        prefs.edit().putInt(KEY_LAYOUT, layoutMode).apply();
        scrollOffsetY = 0f;
        showBanner(layoutMode == 2 ? "DRUM // PURE TEXT" : "DRUM // WIREFRAME ICONS");
        performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);
        invalidate();
    }

    private void showBanner(String msg) {
        bannerMessage = msg;
        bannerUntilMs = SystemClock.uptimeMillis() + 1500L;
    }

    private void checkAndSyncWallpapers(final boolean isDay) {
        if (lastSyncedIsDay != null && lastSyncedIsDay == isDay) return;
        lastSyncedIsDay = isDay;
        final Bitmap sysBmp = isDay ? daySysWall : nightSysWall;
        final Bitmap lockBmp = isDay ? dayLockWall : nightLockWall;
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    WallpaperManager wm = WallpaperManager.getInstance(getContext());
                    if (Build.VERSION.SDK_INT >= 24) {
                        if (sysBmp != null) wm.setBitmap(sysBmp, null, true, WallpaperManager.FLAG_SYSTEM);
                        if (lockBmp != null) wm.setBitmap(lockBmp, null, true, WallpaperManager.FLAG_LOCK);
                    } else if (sysBmp != null) {
                        wm.setBitmap(sysBmp);
                    }
                } catch (Throwable ignored) {
                }
            }
        }).start();
    }

    private void saveFavorites() {
        prefs.edit().putStringSet(KEY_FAVS, new HashSet<>(favoritePackages)).apply();
    }

    private void toggleFavorite(AppEntry entry) {
        if (entry == null) return;
        performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
        if (favoritePackages.contains(entry.packageName)) {
            favoritePackages.remove(entry.packageName);
            showBanner("UNPINNED // " + entry.label.toUpperCase(Locale.US));
        } else {
            favoritePackages.add(entry.packageName);
            showBanner("PINNED // " + entry.label.toUpperCase(Locale.US));
        }
        saveFavorites();
        rebuildVisibleApps();
        invalidate();
    }

    public void reloadInstalledApps() {
        allApps.clear();
        privateApps.clear();
        privateProfileHandle = null;

        String myPkg = getContext().getPackageName();
        UserHandle myUser = Process.myUserHandle();

        LauncherApps launcherApps = (LauncherApps) getContext().getSystemService(Context.LAUNCHER_APPS_SERVICE);
        if (launcherApps != null) {
            List<UserHandle> profiles = launcherApps.getProfiles();
            for (UserHandle profile : profiles) {
                boolean isPrivate = !myUser.equals(profile);
                if (isPrivate) {
                    privateProfileHandle = profile;
                }
                try {
                    List<LauncherActivityInfo> activities = launcherApps.getActivityList(null, profile);
                    for (LauncherActivityInfo info : activities) {
                        ComponentName comp = info.getComponentName();
                        String pkg = comp.getPackageName();
                        if (myPkg.equals(pkg) || "app.olauncher".equals(pkg)) continue;
                        CharSequence cs = info.getLabel();
                        String label = cs != null ? cs.toString().trim() : pkg;
                        String friendly = friendlyLabel(pkg, label);
                        AppEntry entry = new AppEntry(
                                friendly, pkg, comp.getClassName(),
                                classifyIcon(pkg, friendly),
                                comp, profile, isPrivate, false
                        );
                        if (isPrivate) {
                            privateApps.add(entry);
                        } else {
                            allApps.add(entry);
                        }
                    }
                } catch (Throwable ignored) {
                }
            }
        }

        // Fallback if LauncherApps returned nothing for primary user
        if (allApps.isEmpty()) {
            PackageManager pm = getContext().getPackageManager();
            Intent mainIntent = new Intent(Intent.ACTION_MAIN, null);
            mainIntent.addCategory(Intent.CATEGORY_LAUNCHER);
            List<ResolveInfo> resolved = pm.queryIntentActivities(mainIntent, 0);
            for (ResolveInfo ri : resolved) {
                if (ri.activityInfo == null) continue;
                String pkg = ri.activityInfo.packageName;
                if (myPkg.equals(pkg) || "app.olauncher".equals(pkg)) continue;
                CharSequence cs = ri.loadLabel(pm);
                String label = cs != null ? cs.toString().trim() : pkg;
                String friendly = friendlyLabel(pkg, label);
                ComponentName comp = new ComponentName(pkg, ri.activityInfo.name);
                allApps.add(new AppEntry(friendly, pkg, ri.activityInfo.name, classifyIcon(pkg, friendly), comp, myUser, false, false));
            }
        }

        Comparator<AppEntry> byLabel = new Comparator<AppEntry>() {
            @Override
            public int compare(AppEntry a, AppEntry b) {
                return a.label.compareToIgnoreCase(b.label);
            }
        };
        Collections.sort(allApps, byLabel);
        Collections.sort(privateApps, byLabel);

        rebuildVisibleApps();
    }

    private String friendlyLabel(String pkg, String raw) {
        if ("com.brave.browser".equals(pkg)) return "Brave";
        if ("com.google.android.gm".equals(pkg)) return "Gmail";
        if ("com.phonepe.app".equals(pkg)) return "PhonePe";
        if ("com.google.android.dialer".equals(pkg)) return "Phone";
        if ("com.google.android.apps.messaging".equals(pkg)) return "Messages";
        if ("com.google.android.apps.maps".equals(pkg)) return "Maps";
        if ("com.google.android.apps.photos".equals(pkg)) return "Photos";
        return raw;
    }

    private int classifyIcon(String pkg, String label) {
        String s = (pkg + " " + label).toLowerCase(Locale.US);
        if (s.contains("phonepe") || s.contains("paisa") || s.contains("pay") || s.contains("wallet") || s.contains("bank") || s.contains("revolut") || s.contains("axis")) return 11;
        if (s.contains("dialer") || s.equals("phone") || s.contains("telephone")) return 1;
        if (s.contains("whatsapp")) return 12;
        if (s.contains("messaging") || s.contains("message") || s.contains("teams")) return 2;
        if (s.contains("brave") || s.contains("internet") || s.contains("browser") || s.contains("chrome")) return 3;
        if (s.contains("gm") || s.contains("mail") || s.contains("outlook")) return 4;
        if (s.contains("map") || s.contains("uber") || s.contains("compass")) return 5;
        if (s.contains("camera")) return 6;
        if (s.contains("photo") || s.contains("gallery")) return 7;
        if (s.contains("setting")) return 8;
        if (s.contains("clock") || s.contains("alarm")) return 9;
        if (s.contains("docs") || s.contains("note") || s.contains("read") || s.contains("book")) return 10;
        return 0;
    }

    private boolean isPrivateSpaceLocked() {
        if (privateProfileHandle == null) return false;
        try {
            UserManager um = (UserManager) getContext().getSystemService(Context.USER_SERVICE);
            if (um != null) {
                return um.isQuietModeEnabled(privateProfileHandle);
            }
        } catch (Throwable ignored) {
        }
        return false;
    }

    private void rebuildVisibleApps() {
        visibleApps.clear();
        if (activeFilterChar == '◈') {
            if (privateProfileHandle == null) {
                visibleApps.add(new AppEntry("Private Space (Unlock)", "__private_unlock__", "", 8, null, null, true, true));
            } else if (isPrivateSpaceLocked() || privateApps.isEmpty()) {
                visibleApps.add(new AppEntry("Unlock Private Space", "__private_unlock__", "", 8, null, privateProfileHandle, true, true));
            } else {
                visibleApps.add(new AppEntry("Lock Private Space", "__private_lock__", "", 8, null, privateProfileHandle, true, true));
                visibleApps.addAll(privateApps);
            }
        } else if (activeFilterChar == '☆') {
            for (String favPkg : DEFAULT_FAVORITES) {
                if (!favoritePackages.contains(favPkg)) continue;
                for (AppEntry e : allApps) {
                    if (e.packageName.equals(favPkg)) {
                        visibleApps.add(e);
                        break;
                    }
                }
            }
            for (AppEntry e : allApps) {
                if (favoritePackages.contains(e.packageName) && !containsPkg(visibleApps, e.packageName)) {
                    visibleApps.add(e);
                }
            }
            if (visibleApps.isEmpty()) {
                for (int i = 0; i < Math.min(8, allApps.size()); i++) {
                    visibleApps.add(allApps.get(i));
                }
            }
        } else if (activeFilterChar == '○') {
            visibleApps.addAll(allApps);
        } else {
            for (AppEntry e : allApps) {
                if (!e.label.isEmpty() && Character.toUpperCase(e.label.charAt(0)) == activeFilterChar) {
                    visibleApps.add(e);
                }
            }
        }
    }

    private boolean containsPkg(List<AppEntry> list, String pkg) {
        for (AppEntry e : list) {
            if (e.packageName.equals(pkg)) return true;
        }
        return false;
    }

    private int getBatteryPercentage() {
        try {
            BatteryManager bm = (BatteryManager) getContext().getSystemService(Context.BATTERY_SERVICE);
            if (bm != null) {
                int lvl = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
                if (lvl >= 0 && lvl <= 100) return lvl;
            }
        } catch (Throwable ignored) {
        }
        return 100;
    }

    private void refreshNetworkState(boolean force) {
        long now = SystemClock.uptimeMillis();
        if (!force && (now - lastNetCheckMs) < 2500L) return;
        lastNetCheckMs = now;
        try {
            ConnectivityManager cm = (ConnectivityManager) getContext().getSystemService(Context.CONNECTIVITY_SERVICE);
            if (cm != null) {
                Network active = cm.getActiveNetwork();
                NetworkCapabilities caps = active != null ? cm.getNetworkCapabilities(active) : null;
                hasWifi = caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI);
                hasCellular = caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR);
                if (!hasCellular) {
                    for (Network net : cm.getAllNetworks()) {
                        NetworkCapabilities nc = cm.getNetworkCapabilities(net);
                        if (nc != null && nc.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
                            hasCellular = true;
                            break;
                        }
                    }
                }
            }
        } catch (Throwable ignored) {
        }
    }

    private boolean isDayModeActive(Calendar cal) {
        if ("day".equals(dayNightOverride)) return true;
        if ("night".equals(dayNightOverride)) return false;
        int hour = cal.get(Calendar.HOUR_OF_DAY);
        return (hour >= 6 && hour < 18);
    }

    private boolean isZeroFrictionUtility(String pkg) {
        if (pkg == null) return false;
        for (String d : DOCK_PACKAGES) {
            if (d.equals(pkg)) return true;
        }
        if (favoritePackages.contains(pkg)) return true;
        String s = pkg.toLowerCase(Locale.US);
        return s.contains("dialer") || s.contains("messaging") || s.contains("camera")
                || s.contains("settings") || s.contains("deskclock") || s.contains("calendar")
                || s.contains("calculator") || s.contains("authenticator") || s.contains("bank")
                || s.contains("revolut") || s.contains("axis") || s.contains("paypal")
                || s.contains("remitly") || s.contains("digilocker") || s.contains("uidai");
    }

    private float getSafeTopPx() {
        if (Build.VERSION.SDK_INT >= 28) {
            WindowInsets insets = getRootWindowInsets();
            if (insets != null) {
                DisplayCutout cutout = insets.getDisplayCutout();
                if (cutout != null && cutout.getSafeInsetTop() > 0) {
                    return cutout.getSafeInsetTop();
                }
            }
        }
        return dp(52f);
    }

    // =========================================================================
    // MAIN 120HZ RENDERING PIPELINE
    // =========================================================================
    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int w = getWidth();
        int h = getHeight();
        if (w <= 0 || h <= 0) return;

        long nowMs = SystemClock.uptimeMillis();
        Calendar cal = Calendar.getInstance();
        Date nowDate = cal.getTime();
        boolean isDay = isDayModeActive(cal);
        checkAndSyncWallpapers(isDay);

        int batteryPct = getBatteryPercentage();
        refreshNetworkState(false);

        // Monochrome Palette (Day E-Ink Architectural Paper vs Night Obsidian Terminal)
        int bgCol = isDay ? 0xFFE6E5E0 : 0xFF050608;
        int gridCol = isDay ? 0xFFD6D5CE : 0xFF0D0F14;
        int cardFillCol = isDay ? 0xFFDDDCD5 : 0xFF0B0D12;
        int cardBorderCol = isDay ? 0xFFB8B7B0 : 0xFF222630;
        int fgPrimary = isDay ? 0xFF121316 : 0xFFF2F4F8;
        int fgSecondary = isDay ? 0xFF4A4C52 : 0xFFA2A8B4;
        int fgMuted = isDay ? 0xFF888A90 : 0xFF525866;

        // 1. Technical Orthographic Drafting Grid Background (ZERO stars!)
        drawTechnicalGridBackground(canvas, w, h, bgCol, gridCol, fgMuted);

        // If Wake Instrument Overlay is active, render full-screen Horological Astrolabe Lock Screen
        if (wakeOverlayActive) {
            drawWakeInstrumentOverlay(canvas, w, h, cal, nowDate, batteryPct, nowMs, isDay, fgPrimary, fgSecondary, fgMuted, cardFillCol, cardBorderCol);
            postInvalidateOnAnimation();
            return;
        }

        // 2. Top-Center Single Pill Cluster positioned safely BELOW the Pixel 10 Pro punch-hole camera
        float safeTop = getSafeTopPx();
        float clusterCy = safeTop + dp(28f);
        drawMicroGaugeCluster(canvas, w * 0.5f, clusterCy, batteryPct, fgPrimary, fgSecondary, fgMuted, cardFillCol, cardBorderCol);

        // 3. Concentric Mechanical Chrono Dial + Date (no QUANTUM.CORE, no PULSE, no E-INK // DAY)
        float afterChronoY = drawChronoHero(canvas, w, h, cal, nowDate, clusterCy + dp(28f), fgPrimary, fgSecondary, fgMuted, cardFillCol);

        // 4. 3D Kinetic Rotary Drum App Selector (spacious!)
        float dockTopY = h - dp(92);
        drawKinetic3DAppDrum(canvas, w, afterChronoY + dp(12), dockTopY - dp(10), fgPrimary, fgSecondary, fgMuted, cardFillCol, cardBorderCol);

        // 5. Bottom 5-Tool Essential Monochrome Dock (PhonePe, Gmail, WhatsApp, Brave, Maps)
        drawBottomFiveToolDock(canvas, w, h, dockTopY, fgPrimary, fgSecondary, cardFillCol, cardBorderCol);

        // 6. Expanded Right-Edge A-Z Vernier Wave Scrubber
        drawAlphabetRail(canvas, w, h, afterChronoY + dp(10), dockTopY - dp(14), fgPrimary, fgSecondary, fgMuted, cardFillCol);

        // 7. 3-Second Intention Gate Overlay (if user tapped a non-utility app)
        if (pendingGateApp != null) {
            drawIntentionGateOverlay(canvas, w, h, nowMs, isDay, fgPrimary, fgSecondary, fgMuted, cardFillCol, cardBorderCol);
        }

        // 8. Minimalist Technical Toast Banner
        if (bannerMessage != null && nowMs < bannerUntilMs) {
            drawBannerToast(canvas, w, h, fgPrimary, cardFillCol, cardBorderCol);
        }

        postInvalidateOnAnimation();
    }

    private void drawTechnicalGridBackground(Canvas canvas, int w, int h, int bgCol, int gridCol, int crossCol) {
        canvas.drawColor(bgCol);
        uiPaint.setStyle(Paint.Style.STROKE);
        uiPaint.setStrokeWidth(1f);
        uiPaint.setColor(gridCol);

        float step = dp(28);
        for (float x = step; x < w; x += step) {
            canvas.drawLine(x, 0, x, h, uiPaint);
        }
        for (float y = step; y < h; y += step) {
            canvas.drawLine(0, y, w, y, uiPaint);
        }

        // Subtle CAD registration crosshairs '+'
        uiPaint.setColor((crossCol & 0x00FFFFFF) | 0x44000000);
        float cArm = dp(3f);
        for (float x = step * 3; x < w - step; x += step * 4) {
            for (float y = step * 4; y < h - step; y += step * 6) {
                canvas.drawLine(x - cArm, y, x + cArm, y, uiPaint);
                canvas.drawLine(x, y - cArm, x, y + cArm, uiPaint);
            }
        }
    }

    // =========================================================================
    // TOP-RIGHT HOROLOGICAL MICRO-GAUGE TRIO (Direct from Video 00:00 - 00:09)
    // =========================================================================
    private void drawMicroGaugeCluster(Canvas canvas, float cx, float cy, int batteryPct,
                                       int fgPrimary, int fgSecondary, int fgMuted, int cardFill, int cardBorder) {
        float r = dp(16.5f);
        float spacing = dp(46f);
        float g1Cx = cx - spacing; // SYS
        float g2Cx = cx;           // NET
        float g3Cx = cx + spacing; // PWR

        // Subtle enclosing pill capsule around the 3 gauges
        float pillW = spacing * 2f + r * 2f + dp(20f);
        float pillH = r * 2f + dp(18f);
        RectF clusterPill = new RectF(cx - pillW / 2f, cy - r - dp(5f), cx + pillW / 2f, cy + r + dp(13f));
        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(cardFill);
        canvas.drawRoundRect(clusterPill, pillH / 2f, pillH / 2f, uiPaint);
        uiPaint.setStyle(Paint.Style.STROKE);
        uiPaint.setStrokeWidth(dp(1f));
        uiPaint.setColor(cardBorder);
        canvas.drawRoundRect(clusterPill, pillH / 2f, pillH / 2f, uiPaint);

        gaugeDeviceRect.set(g1Cx - r, cy - r, g1Cx + r, cy + r);

        // --- Gauge 1: SYS (Device / Standby Lock Ring) ---
        drawMicroGaugeDial(canvas, g1Cx, cy, r, 24, 1.0f, fgPrimary, fgMuted, cardFill);
        RectF phoneBox = new RectF(g1Cx - dp(3.8f), cy - dp(6.5f), g1Cx + dp(3.8f), cy + dp(6.5f));
        iconPaint.setStrokeWidth(dp(1.25f));
        iconPaint.setColor(fgPrimary);
        canvas.drawRoundRect(phoneBox, dp(1.5f), dp(1.5f), iconPaint);
        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(fgPrimary);
        canvas.drawCircle(g1Cx, cy - dp(4.4f), dp(0.8f), uiPaint);

        // --- Gauge 2: NET (Cellular Signal Caliper Ring + 4 Bars) ---
        drawMicroGaugeDial(canvas, g2Cx, cy, r, 32, hasCellular ? 0.85f : 0.2f, fgPrimary, fgMuted, cardFill);
        for (int b = 0; b < 4; b++) {
            float bh = dp(2.8f + b * 2.0f);
            float bx = g2Cx - dp(5.5f) + b * dp(3.2f);
            float by = cy + dp(4.5f);
            uiPaint.setColor(hasCellular ? fgPrimary : fgMuted);
            canvas.drawRoundRect(new RectF(bx, by - bh, bx + dp(1.9f), by), dp(0.7f), dp(0.7f), uiPaint);
        }

        // --- Gauge 3: PWR (Radial Battery % + Wi-Fi Dot) ---
        drawMicroGaugeDial(canvas, g3Cx, cy, r, 32, batteryPct / 100f, fgPrimary, fgMuted, cardFill);
        monoPaint.setTextSize(sp(8.2f));
        monoPaint.setColor(fgPrimary);
        String pctStr = batteryPct + "%";
        float tw = monoPaint.measureText(pctStr);
        canvas.drawText(pctStr, g3Cx - tw / 2f, cy + dp(2.8f), monoPaint);
        uiPaint.setColor(hasWifi ? fgPrimary : fgMuted);
        canvas.drawCircle(g3Cx, cy - dp(8.0f), dp(1.25f), uiPaint);

        // Micro-captions underneath each gauge inside the pill
        monoPaint.setTextSize(sp(6.8f));
        monoPaint.setColor(fgMuted);
        String[] labels = new String[]{"SYS", "NET", "PWR"};
        float[] centers = new float[]{g1Cx, g2Cx, g3Cx};
        for (int i = 0; i < 3; i++) {
            float lw = monoPaint.measureText(labels[i]);
            canvas.drawText(labels[i], centers[i] - lw / 2f, cy + r + dp(9.5f), monoPaint);
        }
    }

    private void drawMicroGaugeDial(Canvas canvas, float cx, float cy, float r, int ticks, float activeFraction, int fgPrimary, int fgMuted, int cardFill) {
        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor((cardFill & 0x00FFFFFF) | 0xCC000000);
        if (Color.red(cardFill) > 128) {
            uiPaint.setColor(0xCCE0DFD8);
        }
        canvas.drawCircle(cx, cy, r, uiPaint);

        dialTickPaint.setStrokeWidth(dp(1.1f));
        int activeTicks = Math.round(ticks * activeFraction);
        for (int i = 0; i < ticks; i++) {
            double angle = Math.toRadians(-90 + (i * 360.0 / ticks));
            float cos = (float) Math.cos(angle);
            float sin = (float) Math.sin(angle);
            float r0 = r - dp(3.2f);
            dialTickPaint.setColor(i < activeTicks ? fgPrimary : fgMuted);
            canvas.drawLine(cx + r0 * cos, cy + r0 * sin, cx + r * cos, cy + r * sin, dialTickPaint);
        }
    }

    // =========================================================================
    // CONCENTRIC HOROLOGICAL CHRONO DIAL (Clean, zero clutter)
    // =========================================================================
    private float drawChronoHero(Canvas canvas, int w, int h, Calendar cal, Date nowDate, float topBarrierY,
                                 int fgPrimary, int fgSecondary, int fgMuted, int cardFill) {
        float dialCx = dp(16);
        float rInner = dp(98);
        float rOuter = dp(148);
        float dialCy = topBarrierY + rOuter + dp(12);

        int hour = cal.get(Calendar.HOUR_OF_DAY);
        int minute = cal.get(Calendar.MINUTE);
        int second = cal.get(Calendar.SECOND);
        int millis = cal.get(Calendar.MILLISECOND);

        float exactSec = second + (millis / 1000f);
        float exactMin = minute + (exactSec / 60f);

        // Subtle continuous guide circles (like Video 00:00 astrolabe)
        dialTickPaint.setStrokeWidth(dp(0.7f));
        dialTickPaint.setColor((fgMuted & 0x00FFFFFF) | 0x55000000);
        canvas.drawArc(new RectF(dialCx - rOuter, dialCy - rOuter, dialCx + rOuter, dialCy + rOuter), -75, 150, false, dialTickPaint);
        canvas.drawArc(new RectF(dialCx - rInner, dialCy - rInner, dialCx + rInner, dialCy + rInner), -75, 150, false, dialTickPaint);

        // Outer seconds wheel
        for (int s = 0; s < 60; s++) {
            float diff = s - exactSec;
            if (diff > 30f) diff -= 60f;
            if (diff < -30f) diff += 60f;
            float angleDeg = diff * 6f;
            if (Math.abs(angleDeg) > 74f) continue;

            double rad = Math.toRadians(angleDeg);
            float cos = (float) Math.cos(rad);
            float sin = (float) Math.sin(rad);

            boolean isMajor = (s % 5 == 0);
            float fade = Math.max(0f, 1f - Math.abs(angleDeg) / 74f);
            int baseCol = isMajor ? fgPrimary : fgMuted;
            int alpha = (int) ((isMajor ? 220 : 110) * fade);

            float r0 = rOuter - dp(isMajor ? 6.5f : 3.2f);
            dialTickPaint.setStrokeWidth(dp(isMajor ? 1.4f : 0.8f));
            dialTickPaint.setColor((baseCol & 0x00FFFFFF) | (alpha << 24));
            canvas.drawLine(dialCx + r0 * cos, dialCy + r0 * sin, dialCx + rOuter * cos, dialCy + rOuter * sin, dialTickPaint);

            if (isMajor && Math.abs(angleDeg) > 9f) {
                monoPaint.setTextSize(sp(9f));
                monoPaint.setColor((fgSecondary & 0x00FFFFFF) | ((int) (185 * fade) << 24));
                String num = String.format(Locale.US, "%02d", s);
                float nr = rOuter - dp(17f);
                float nw = monoPaint.measureText(num);
                canvas.drawText(num, dialCx + nr * cos - nw / 2f, dialCy + nr * sin + dp(3.2f), monoPaint);
            }
        }

        // Inner minutes wheel
        for (int m = 0; m < 60; m++) {
            float diff = m - exactMin;
            if (diff > 30f) diff -= 60f;
            if (diff < -30f) diff += 60f;
            float angleDeg = diff * 6f;
            if (Math.abs(angleDeg) > 72f) continue;

            double rad = Math.toRadians(angleDeg);
            float cos = (float) Math.cos(rad);
            float sin = (float) Math.sin(rad);

            boolean isMajor = (m % 5 == 0);
            float fade = Math.max(0f, 1f - Math.abs(angleDeg) / 72f);
            int baseCol = isMajor ? fgPrimary : fgMuted;
            int alpha = (int) ((isMajor ? 235 : 120) * fade);

            float r0 = rInner - dp(isMajor ? 6.5f : 3.2f);
            dialTickPaint.setStrokeWidth(dp(isMajor ? 1.5f : 0.9f));
            dialTickPaint.setColor((baseCol & 0x00FFFFFF) | (alpha << 24));
            canvas.drawLine(dialCx + r0 * cos, dialCy + r0 * sin, dialCx + rInner * cos, dialCy + rInner * sin, dialTickPaint);

            if (isMajor && Math.abs(angleDeg) > 10f) {
                monoPaint.setTextSize(sp(10f));
                monoPaint.setColor((fgPrimary & 0x00FFFFFF) | ((int) (205 * fade) << 24));
                String num = String.format(Locale.US, "%02d", m);
                float nr = rInner - dp(17f);
                float nw = monoPaint.measureText(num);
                canvas.drawText(num, dialCx + nr * cos - nw / 2f, dialCy + nr * sin + dp(3.5f), monoPaint);
            }
        }

        // Oversized Bold Hour
        clockPaint.setTextSize(sp(38f));
        clockPaint.setColor(fgPrimary);
        String hourStr = String.format(Locale.US, "%02d", hour);
        canvas.drawText(hourStr, dp(22), dialCy + dp(13.5f), clockPaint);

        // Stadium Pill framing aligned Minute + Second
        float pillLeft = dialCx + rInner - dp(34);
        float pillRight = dialCx + rOuter + dp(8);
        RectF readoutPill = new RectF(pillLeft, dialCy - dp(16.5f), pillRight, dialCy + dp(16.5f));

        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(cardFill);
        canvas.drawRoundRect(readoutPill, dp(16.5f), dp(16.5f), uiPaint);

        uiPaint.setStyle(Paint.Style.STROKE);
        uiPaint.setStrokeWidth(dp(1.4f));
        uiPaint.setColor(fgPrimary);
        canvas.drawRoundRect(readoutPill, dp(16.5f), dp(16.5f), uiPaint);

        // Triangular Vernier Caliper Index Pointers ▲ / ▽ on the pill (from Video 00:00)
        drawTrianglePointer(canvas, dialCx + rOuter - dp(16), readoutPill.top - dp(4), dp(3.2f), true, fgPrimary);
        drawTrianglePointer(canvas, dialCx + rInner - dp(16), readoutPill.bottom + dp(4), dp(3.2f), false, fgPrimary);

        monoPaint.setTextSize(sp(14.5f));
        monoPaint.setColor(fgPrimary);
        canvas.drawText(String.format(Locale.US, "%02d", minute), dialCx + rInner - dp(24), dialCy + dp(5f), monoPaint);

        monoPaint.setTextSize(sp(12f));
        monoPaint.setColor(fgSecondary);
        canvas.drawText(String.format(Locale.US, "%02d", second), dialCx + rOuter - dp(24), dialCy + dp(4.5f), monoPaint);

        // Right-side Date & Weekday (Clean, zero redundant mode text)
        String dateLine = new SimpleDateFormat("dd MMM yyyy", Locale.US).format(nowDate).toUpperCase(Locale.US);
        String dayLine = new SimpleDateFormat("EEEE", Locale.US).format(nowDate).toUpperCase(Locale.US);

        subTextPaint.setTextSize(sp(10.5f));
        subTextPaint.setLetterSpacing(0.18f);
        subTextPaint.setColor(fgPrimary);
        float rightAnchor = w - dp(24);
        canvas.drawText(dateLine, rightAnchor - subTextPaint.measureText(dateLine), dialCy - dp(3), subTextPaint);

        subTextPaint.setColor(fgSecondary);
        canvas.drawText(dayLine, rightAnchor - subTextPaint.measureText(dayLine), dialCy + dp(14), subTextPaint);

        return dialCy + rOuter + dp(10);
    }

    private void drawTrianglePointer(Canvas canvas, float cx, float cy, float r, boolean pointDown, int color) {
        Path p = new Path();
        if (pointDown) {
            p.moveTo(cx - r, cy - r);
            p.lineTo(cx + r, cy - r);
            p.lineTo(cx, cy + r);
        } else {
            p.moveTo(cx - r, cy + r);
            p.lineTo(cx + r, cy + r);
            p.lineTo(cx, cy - r);
        }
        p.close();
        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(color);
        canvas.drawPath(p, uiPaint);
    }

    // =========================================================================
    // INNOVATION 2: QUANTUM.CORE 3D POINT-CLOUD GLOBE + VECTOR FLOW FIELD
    // (Direct from Video 00:01 & 00:07 - 00:09)
    // =========================================================================
    private float drawQuantumCoreHud(Canvas canvas, int w, int h, float topY, long nowMs,
                                     int fgPrimary, int fgSecondary, int fgMuted, int cardFill, int cardBorder) {
        float cardH = dp(148);
        float left = dp(22);
        float right = w - dp(38);
        quantumCardRect.set(left, topY, right, topY + cardH);
        quantumHeaderRect.set(left, topY, right, topY + dp(26));

        // Framed technical CAD box
        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(cardFill);
        canvas.drawRoundRect(quantumCardRect, dp(10), dp(10), uiPaint);

        uiPaint.setStyle(Paint.Style.STROKE);
        uiPaint.setStrokeWidth(dp(1f));
        uiPaint.setColor(cardBorder);
        canvas.drawRoundRect(quantumCardRect, dp(10), dp(10), uiPaint);

        // Header line: "QUANTUM.CORE" + "[-] [+] [×]" (from Video 00:07)
        monoPaint.setTextSize(sp(10f));
        monoPaint.setColor(fgPrimary);
        canvas.drawText("QUANTUM.CORE", left + dp(12), topY + dp(17), monoPaint);

        // Tiny [-][+][x] circles on top-right of card
        String[] glyphs = new String[]{"-", "+", "×"};
        for (int i = 0; i < 3; i++) {
            float gcx = right - dp(44) + i * dp(15);
            float gcy = topY + dp(13.5f);
            uiPaint.setStyle(Paint.Style.STROKE);
            uiPaint.setColor(fgMuted);
            canvas.drawCircle(gcx, gcy, dp(5.5f), uiPaint);
            monoPaint.setTextSize(sp(8f));
            monoPaint.setColor(fgSecondary);
            float gw = monoPaint.measureText(glyphs[i]);
            canvas.drawText(glyphs[i], gcx - gw / 2f, gcy + dp(2.8f), monoPaint);
        }

        canvas.drawLine(left + dp(8), topY + dp(24), right - dp(8), topY + dp(24), uiPaint);

        // --- Left Half: 3D Rotating Point-Cloud Sphere ---
        float globeCx = left + (quantumCardRect.width() * 0.27f);
        float globeCy = topY + dp(86);
        float globeR = dp(46);
        draw3DPointCloudGlobe(canvas, globeCx, globeCy, globeR, nowMs, fgPrimary, fgSecondary, fgMuted);

        // Vertical divider inside card
        float midX = left + quantumCardRect.width() * 0.54f;
        uiPaint.setColor(cardBorder);
        canvas.drawLine(midX, topY + dp(30), midX, topY + cardH - dp(8), uiPaint);

        // --- Right Half: Magnetic Vector Arrow Flow Field (Video 00:01 & 00:08) + Dual-Sine Phase Wave ---
        float flowLeft = midX + dp(10);
        float flowRight = right - dp(28);
        float flowTop = topY + dp(34);
        float flowBottom = topY + cardH - dp(12);
        drawMagneticVectorFlowField(canvas, flowLeft, flowTop, flowRight, flowBottom, nowMs, fgPrimary, fgSecondary, fgMuted);

        // Far-Right Vertical Dual-Sine Phase Analyzer (Video 00:07)
        float sineCx = right - dp(15);
        drawVerticalPhaseWave(canvas, sineCx, flowTop, flowBottom, nowMs, fgPrimary, fgMuted);

        return quantumCardRect.bottom;
    }

    private void draw3DPointCloudGlobe(Canvas canvas, float cx, float cy, float radius, long nowMs,
                                       int fgPrimary, int fgSecondary, int fgMuted) {
        // Outer wireframe rim
        dialTickPaint.setStrokeWidth(dp(0.8f));
        dialTickPaint.setColor((fgMuted & 0x00FFFFFF) | 0x66000000);
        canvas.drawCircle(cx, cy, radius, dialTickPaint);

        float rotY = (nowMs % 24000L) / 24000f * 6.28318f;
        float tiltX = 0.35f;
        float cosTilt = (float) Math.cos(tiltX);
        float sinTilt = (float) Math.sin(tiltX);

        uiPaint.setStyle(Paint.Style.FILL);

        // Project 3D lat/long grid of points
        int latSteps = 11;
        int lonSteps = 22;
        for (int i = 1; i < latSteps; i++) {
            double lat = -Math.PI / 2 + (i * Math.PI / latSteps);
            float cosLat = (float) Math.cos(lat);
            float sinLat = (float) Math.sin(lat);

            for (int j = 0; j < lonSteps; j++) {
                double lon = (j * 2 * Math.PI / lonSteps) + rotY;
                float x3 = (float) (cosLat * Math.sin(lon));
                float y3 = sinLat;
                float z3 = (float) (cosLat * Math.cos(lon));

                // Apply X-axis tilt
                float yTilt = y3 * cosTilt - z3 * sinTilt;
                float zTilt = y3 * sinTilt + z3 * cosTilt;

                float px = cx + x3 * radius;
                float py = cy + yTilt * radius;

                if (zTilt >= -0.15f) {
                    int alpha = (int) (75 + Math.max(0f, zTilt) * 180);
                    uiPaint.setColor((fgPrimary & 0x00FFFFFF) | (alpha << 24));
                    float dotR = dp(zTilt > 0.4f ? 1.3f : 0.9f);
                    canvas.drawCircle(px, py, dotR, uiPaint);
                } else {
                    uiPaint.setColor((fgMuted & 0x00FFFFFF) | 0x26000000);
                    canvas.drawCircle(px, py, dp(0.6f), uiPaint);
                }
            }
        }

        // Technical altitude callouts ("2050" / "3000" from Video 00:07)
        monoPaint.setTextSize(sp(7.5f));
        monoPaint.setColor(fgSecondary);
        canvas.drawText("2050", cx + radius + dp(4), cy - radius * 0.4f, monoPaint);
        canvas.drawText("3000", cx + radius + dp(4), cy + dp(3), monoPaint);
    }

    private void drawMagneticVectorFlowField(Canvas canvas, float left, float top, float right, float bottom,
                                             long nowMs, int fgPrimary, int fgSecondary, int fgMuted) {
        int cols = 6;
        int rows = 5;
        float cellW = (right - left) / cols;
        float cellH = (bottom - top) / rows;

        // Moving harmonic focal attractor
        float t = (nowMs % 10000L) / 10000f * 6.28318f;
        float attX = (left + right) * 0.5f + (float) Math.cos(t) * (right - left) * 0.25f;
        float attY = (top + bottom) * 0.5f + (float) Math.sin(t * 1.5f) * (bottom - top) * 0.25f;

        dialTickPaint.setStrokeWidth(dp(1.0f));
        uiPaint.setStyle(Paint.Style.FILL);

        for (int r = 0; r < rows; r++) {
            for (int c = 0; c < cols; c++) {
                float vx = left + (c + 0.5f) * cellW;
                float vy = top + (r + 0.5f) * cellH;

                float dx = attX - vx;
                float dy = attY - vy;
                double angle = Math.atan2(dy, dx) + 0.45 * Math.sin(t + r * 0.6 + c * 0.4);
                float len = dp(7.5f);
                float ex = vx + (float) Math.cos(angle) * len;
                float ey = vy + (float) Math.sin(angle) * len;

                dialTickPaint.setColor((r + c) % 2 == 0 ? fgPrimary : fgSecondary);
                canvas.drawLine(vx, vy, ex, ey, dialTickPaint);

                // Arrowhead tip dot
                uiPaint.setColor(fgPrimary);
                canvas.drawCircle(ex, ey, dp(1.2f), uiPaint);
            }
        }
    }

    private void drawVerticalPhaseWave(Canvas canvas, float cx, float top, float bottom, long nowMs, int fgPrimary, int fgMuted) {
        dialTickPaint.setStrokeWidth(dp(0.8f));
        dialTickPaint.setColor(fgMuted);
        canvas.drawLine(cx, top, cx, bottom, dialTickPaint);

        Path p1 = new Path();
        float phase = (nowMs % 6000L) / 6000f * 6.28318f;
        int steps = 28;
        for (int i = 0; i <= steps; i++) {
            float frac = (float) i / steps;
            float y = top + frac * (bottom - top);
            float x = cx + (float) Math.sin(frac * 10f + phase) * dp(5.5f);
            if (i == 0) p1.moveTo(x, y);
            else p1.lineTo(x, y);
        }
        dialTickPaint.setStrokeWidth(dp(1.1f));
        dialTickPaint.setColor(fgPrimary);
        canvas.drawPath(p1, dialTickPaint);
    }

    // =========================================================================
    // INNOVATION 3A: 3D KINETIC ROTARY DRUM APP SELECTOR (Video 00:04 - 00:06)
    // =========================================================================
    private void drawKinetic3DAppDrum(Canvas canvas, int w, float topY, float bottomY,
                                      int fgPrimary, int fgSecondary, int fgMuted, int cardFill, int cardBorder) {
        appRowRects.clear();
        boolean showIcons = (layoutMode != 2);

        float rowH = dp(48f);
        float viewportH = Math.max(dp(100), bottomY - topY);
        float totalContentH = visibleApps.size() * rowH;
        maxScrollY = Math.max(0f, totalContentH - viewportH);
        if (scrollOffsetY > maxScrollY) scrollOffsetY = maxScrollY;
        if (scrollOffsetY < 0f) scrollOffsetY = 0f;

        float drumCenterY = (topY + bottomY) * 0.5f;
        float drumRadius = viewportH * 0.58f;

        canvas.save();
        canvas.clipRect(0, topY, w - dp(42), bottomY);

        float baseLeft = dp(24f);
        float baseRight = w - dp(48f);

        for (int i = 0; i < visibleApps.size(); i++) {
            float ry = topY + i * rowH - scrollOffsetY;
            float cy = ry + rowH * 0.5f;

            // Compute 3D cylindrical drum angle (-1..+1 around drumCenterY)
            float normDist = (cy - drumCenterY) / drumRadius;
            float clamped = Math.max(-1f, Math.min(1f, normDist));
            float cosTheta = (float) Math.cos(clamped * 1.15f); // 1.0 at center, tapers toward top/bottom edges
            float scale = 0.82f + 0.18f * cosTheta;
            float indentX = (1f - cosTheta) * dp(28f); // 3D cylindrical curve recession

            RectF rowRect = new RectF(
                    baseLeft + indentX,
                    ry + dp(2.5f),
                    baseRight - indentX * 0.4f,
                    ry + rowH - dp(2.5f)
            );
            appRowRects.add(rowRect);

            if (ry + rowH < topY || ry > bottomY) continue;

            AppEntry app = visibleApps.get(i);
            int alpha = (int) (105 + 150 * cosTheta);

            // Faceted technical drum card around focused/near-center items (Video 00:05-00:06)
            if (i == pressedAppIndex || cosTheta > 0.86f) {
                uiPaint.setStyle(Paint.Style.FILL);
                uiPaint.setColor(i == pressedAppIndex ? ((fgPrimary & 0x00FFFFFF) | 0x28000000) : cardFill);
                canvas.drawRoundRect(rowRect, dp(8), dp(8), uiPaint);

                uiPaint.setStyle(Paint.Style.STROKE);
                uiPaint.setStrokeWidth(dp(cosTheta > 0.94f ? 1.2f : 0.8f));
                uiPaint.setColor(cosTheta > 0.94f ? fgSecondary : cardBorder);
                canvas.drawRoundRect(rowRect, dp(8), dp(8), uiPaint);
            }

            float textX = rowRect.left + dp(14);
            if (showIcons) {
                float iconCx = rowRect.left + dp(22);
                drawVectorAppIcon(canvas, app.iconKind, app.label, iconCx, cy, dp(8f * scale), (fgPrimary & 0x00FFFFFF) | (alpha << 24));
                textX = rowRect.left + dp(46);
            }

            textPaint.setTextSize(sp(15.5f * scale));
            textPaint.setLetterSpacing(0.04f);
            textPaint.setColor((fgPrimary & 0x00FFFFFF) | (alpha << 24));
            canvas.drawText(app.label, textX, cy + dp(5.2f * scale), textPaint);

            // Technical module tag on the right of the 3D drum card (e.g. "MOD.01")
            monoPaint.setTextSize(sp(8.5f * scale));
            monoPaint.setColor((fgMuted & 0x00FFFFFF) | ((int) (alpha * 0.75f) << 24));
            String modTag = app.isActionRow
                    ? "SYS.VAULT"
                    : (app.isPrivateSpace
                        ? "PVT.SPACE"
                        : (favoritePackages.contains(app.packageName)
                            ? String.format(Locale.US, "CORE.%02d", i + 1)
                            : "EXT.GATE"));
            float mw = monoPaint.measureText(modTag);
            canvas.drawText(modTag, rowRect.right - mw - dp(12), cy + dp(3.5f * scale), monoPaint);
        }

        canvas.restore();
    }

    // =========================================================================
    // INNOVATION 3B: BOTTOM 5-TOOL ESSENTIAL MONOCHROME DOCK
    // (A3: PhonePe, Gmail, WhatsApp, Brave, Maps — Video 00:00 - 00:06)
    // =========================================================================
    private void drawBottomFiveToolDock(Canvas canvas, int w, int h, float topY,
                                        int fgPrimary, int fgSecondary, int cardFill, int cardBorder) {
        RectF dockBar = new RectF(dp(18), topY, w - dp(18), h - dp(22));
        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(cardFill);
        canvas.drawRoundRect(dockBar, dp(22), dp(22), uiPaint);

        uiPaint.setStyle(Paint.Style.STROKE);
        uiPaint.setStrokeWidth(dp(1.1f));
        uiPaint.setColor(cardBorder);
        canvas.drawRoundRect(dockBar, dp(22), dp(22), uiPaint);

        float slotW = dockBar.width() / 5f;
        int[] dockIcons = new int[]{11, 4, 12, 3, 5}; // PhonePe, Gmail, WhatsApp, Brave, Maps

        for (int i = 0; i < 5; i++) {
            float sx = dockBar.left + i * slotW;
            dockSlotRects[i].set(sx, dockBar.top, sx + slotW, dockBar.bottom);
            float cx = dockSlotRects[i].centerX();
            float cy = dockBar.centerY() - dp(5f);

            if (i == pressedDockIndex) {
                uiPaint.setStyle(Paint.Style.FILL);
                uiPaint.setColor((fgPrimary & 0x00FFFFFF) | 0x24000000);
                canvas.drawCircle(cx, dockBar.centerY(), dp(24), uiPaint);
            }

            drawVectorAppIcon(canvas, dockIcons[i], DOCK_LABELS[i], cx, cy, dp(10f), fgPrimary);

            monoPaint.setTextSize(sp(7.8f));
            monoPaint.setColor(fgSecondary);
            String lbl = DOCK_LABELS[i].toUpperCase(Locale.US);
            float lw = monoPaint.measureText(lbl);
            canvas.drawText(lbl, cx - lw / 2f, dockBar.bottom - dp(7.5f), monoPaint);
        }
    }

    private void drawVectorAppIcon(Canvas canvas, int kind, String label, float cx, float cy, float r, int color) {
        iconPaint.setStyle(Paint.Style.STROKE);
        iconPaint.setStrokeWidth(dp(1.5f));
        iconPaint.setColor(color);

        switch (kind) {
            case 1: { // Phone receiver
                RectF arc = new RectF(cx - r, cy - r, cx + r, cy + r);
                canvas.drawArc(arc, 125, 110, false, iconPaint);
                canvas.drawCircle(cx - r * 0.45f, cy - r * 0.65f, dp(2.0f), iconPaint);
                canvas.drawCircle(cx - r * 0.45f, cy + r * 0.65f, dp(2.0f), iconPaint);
                break;
            }
            case 2: { // Messages bubble
                RectF b = new RectF(cx - r, cy - r * 0.8f, cx + r, cy + r * 0.65f);
                canvas.drawRoundRect(b, dp(4.5f), dp(4.5f), iconPaint);
                canvas.drawLine(cx - r * 0.4f, b.bottom, cx - r * 0.7f, cy + r, iconPaint);
                break;
            }
            case 3: { // Brave / Saturn Ringed Globe
                canvas.drawCircle(cx, cy, r * 0.72f, iconPaint);
                canvas.save();
                canvas.rotate(-24f, cx, cy);
                RectF ring = new RectF(cx - r * 1.25f, cy - r * 0.35f, cx + r * 1.25f, cy + r * 0.35f);
                canvas.drawOval(ring, iconPaint);
                canvas.restore();
                break;
            }
            case 4: { // Gmail Envelope M
                RectF env = new RectF(cx - r, cy - r * 0.72f, cx + r, cy + r * 0.72f);
                canvas.drawRoundRect(env, dp(2f), dp(2f), iconPaint);
                Path flap = new Path();
                flap.moveTo(env.left, env.top);
                flap.lineTo(cx, cy + dp(1f));
                flap.lineTo(env.right, env.top);
                canvas.drawPath(flap, iconPaint);
                break;
            }
            case 5: { // Maps Navigation Pin
                canvas.drawCircle(cx, cy - r * 0.2f, r * 0.65f, iconPaint);
                canvas.drawCircle(cx, cy - r * 0.2f, r * 0.22f, iconPaint);
                canvas.drawLine(cx - r * 0.5f, cy + r * 0.15f, cx, cy + r, iconPaint);
                canvas.drawLine(cx + r * 0.5f, cy + r * 0.15f, cx, cy + r, iconPaint);
                break;
            }
            case 6: { // Camera
                RectF cam = new RectF(cx - r, cy - r * 0.65f, cx + r, cy + r * 0.75f);
                canvas.drawRoundRect(cam, dp(2.5f), dp(2.5f), iconPaint);
                canvas.drawCircle(cx, cy + dp(0.5f), r * 0.38f, iconPaint);
                break;
            }
            case 7: { // Photos Pinwheel
                for (int a = 0; a < 4; a++) {
                    canvas.save();
                    canvas.rotate(a * 90f, cx, cy);
                    RectF leaf = new RectF(cx, cy - r * 0.75f, cx + r * 0.75f, cy);
                    canvas.drawRoundRect(leaf, dp(2.8f), dp(2.8f), iconPaint);
                    canvas.restore();
                }
                break;
            }
            case 8: { // Settings Hexagon Gear
                canvas.drawCircle(cx, cy, r * 0.38f, iconPaint);
                canvas.drawCircle(cx, cy, r * 0.85f, iconPaint);
                for (int a = 0; a < 6; a++) {
                    double rad = Math.toRadians(a * 60);
                    canvas.drawLine(
                            cx + (float) Math.cos(rad) * r * 0.75f,
                            cy + (float) Math.sin(rad) * r * 0.75f,
                            cx + (float) Math.cos(rad) * r * 1.05f,
                            cy + (float) Math.sin(rad) * r * 1.05f,
                            iconPaint
                    );
                }
                break;
            }
            case 9: { // Clock
                canvas.drawCircle(cx, cy, r * 0.9f, iconPaint);
                canvas.drawLine(cx, cy, cx, cy - r * 0.5f, iconPaint);
                canvas.drawLine(cx, cy, cx + r * 0.45f, cy, iconPaint);
                break;
            }
            case 11: { // PhonePe / Payment Hexagon Shield + '₹' bar glyph
                Path hex = new Path();
                for (int a = 0; a < 6; a++) {
                    double rad = Math.toRadians(-90 + a * 60);
                    float hx = cx + (float) Math.cos(rad) * r;
                    float hy = cy + (float) Math.sin(rad) * r;
                    if (a == 0) hex.moveTo(hx, hy);
                    else hex.lineTo(hx, hy);
                }
                hex.close();
                canvas.drawPath(hex, iconPaint);
                canvas.drawLine(cx - r * 0.38f, cy - r * 0.32f, cx + r * 0.38f, cy - r * 0.32f, iconPaint);
                canvas.drawLine(cx - r * 0.38f, cy, cx + r * 0.25f, cy, iconPaint);
                canvas.drawLine(cx - r * 0.1f, cy, cx + r * 0.32f, cy + r * 0.48f, iconPaint);
                break;
            }
            case 12: { // WhatsApp Chat Circle + Inner Wave
                canvas.drawCircle(cx, cy, r * 0.92f, iconPaint);
                canvas.drawLine(cx - r * 0.65f, cy + r * 0.65f, cx - r * 0.95f, cy + r * 0.95f, iconPaint);
                RectF innerArc = new RectF(cx - r * 0.45f, cy - r * 0.45f, cx + r * 0.45f, cy + r * 0.45f);
                canvas.drawArc(innerArc, 30, 210, false, iconPaint);
                break;
            }
            default: {
                canvas.drawCircle(cx, cy, r * 0.85f, iconPaint);
                if (label != null && !label.isEmpty()) {
                    monoPaint.setTextSize(sp(9f));
                    monoPaint.setColor(color);
                    String ch = label.substring(0, 1).toUpperCase(Locale.US);
                    float cw = monoPaint.measureText(ch);
                    canvas.drawText(ch, cx - cw / 2f, cy + dp(3.2f), monoPaint);
                }
                break;
            }
        }
    }

    // =========================================================================
    // EXPANDED RIGHT-EDGE A-Z VERNIER WAVE SCRUBBER
    // =========================================================================
    private void drawAlphabetRail(Canvas canvas, int w, int h, float railTop, float railBottom,
                                  int fgPrimary, int fgSecondary, int fgMuted, int cardFill) {
        float railX = w - dp(16);
        int count = RAIL_CHARS.length();
        float stepY = (railBottom - railTop) / (count - 1);

        subTextPaint.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        subTextPaint.setLetterSpacing(0f);

        for (int i = 0; i < count; i++) {
            char c = RAIL_CHARS.charAt(i);
            float cy = railTop + i * stepY;
            float offsetX = 0f;
            float scaleBoost = 0f;

            if (isScrubbingRail && scrubY >= 0) {
                float dist = Math.abs(cy - scrubY);
                float waveRadius = dp(88f);
                if (dist < waveRadius) {
                    float norm = 1f - (dist / waveRadius);
                    float curve = norm * norm;
                    offsetX = -dp(42f) * curve;
                    scaleBoost = 12f * curve;
                }
            }

            // Vernier caliper tick on far right edge
            dialTickPaint.setStrokeWidth(dp(scaleBoost > 2f ? 1.4f : 0.7f));
            dialTickPaint.setColor(scaleBoost > 2f ? fgPrimary : fgMuted);
            canvas.drawLine(w - dp(5), cy, w, cy, dialTickPaint);

            boolean isSelected = (c == activeFilterChar);
            subTextPaint.setTextSize(sp(11f + scaleBoost));
            subTextPaint.setColor(isSelected ? fgPrimary : (scaleBoost > 2f ? fgPrimary : fgSecondary));
            String s = String.valueOf(c);
            float cw = subTextPaint.measureText(s);
            canvas.drawText(s, railX + offsetX - cw / 2f, cy + dp(3.8f), subTextPaint);
        }

        if (isScrubbingRail && scrubY >= 0) {
            float bubbleCx = w - dp(104);
            float bubbleCy = Math.max(railTop, Math.min(railBottom, scrubY));
            float bubbleR = dp(34);

            uiPaint.setStyle(Paint.Style.FILL);
            uiPaint.setColor(cardFill);
            canvas.drawCircle(bubbleCx, bubbleCy, bubbleR, uiPaint);

            uiPaint.setStyle(Paint.Style.STROKE);
            uiPaint.setStrokeWidth(dp(1.8f));
            uiPaint.setColor(fgPrimary);
            canvas.drawCircle(bubbleCx, bubbleCy, bubbleR, uiPaint);

            clockPaint.setTextSize(sp(26f));
            clockPaint.setColor(fgPrimary);
            String s = String.valueOf(activeFilterChar);
            float cw = clockPaint.measureText(s);
            canvas.drawText(s, bubbleCx - cw / 2f, bubbleCy + dp(9.5f), clockPaint);
        }
    }

    // =========================================================================
    // INNOVATION 5: 3-SECOND INTENTION GATE OVERLAY
    // =========================================================================
    private void drawIntentionGateOverlay(Canvas canvas, int w, int h, long nowMs, boolean isDay,
                                          int fgPrimary, int fgSecondary, int fgMuted, int cardFill, int cardBorder) {
        long elapsed = nowMs - gateStartMs;
        if (elapsed >= GATE_DURATION_MS) {
            AppEntry target = pendingGateApp;
            pendingGateApp = null;
            resetToFavorites();
            launchAppImmediate(target);
            return;
        }

        float progress = (float) elapsed / (float) GATE_DURATION_MS;
        float remainingSec = (GATE_DURATION_MS - elapsed) / 1000f;

        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(isDay ? 0xEEEDEAE4 : 0xEE050608);
        canvas.drawRect(0, 0, w, h, uiPaint);

        float cx = w * 0.5f;
        float cy = h * 0.46f;
        float rOuter = dp(115);

        // Rotating Vernier countdown ring
        int ticks = 60;
        int activeTicks = Math.round(ticks * progress);
        dialTickPaint.setStrokeWidth(dp(1.6f));
        for (int i = 0; i < ticks; i++) {
            double rad = Math.toRadians(-90 + (i * 360.0 / ticks));
            float cos = (float) Math.cos(rad);
            float sin = (float) Math.sin(rad);
            float r0 = rOuter - dp(i % 5 == 0 ? 10f : 5f);
            dialTickPaint.setColor(i <= activeTicks ? fgPrimary : fgMuted);
            canvas.drawLine(cx + r0 * cos, cy + r0 * sin, cx + rOuter * cos, cy + rOuter * sin, dialTickPaint);
        }

        monoPaint.setTextSize(sp(11f));
        monoPaint.setColor(fgSecondary);
        String header = "INTENTION.GATE // MINDFUL PAUSE";
        canvas.drawText(header, cx - monoPaint.measureText(header) / 2f, cy - rOuter - dp(28), monoPaint);

        clockPaint.setTextSize(sp(36f));
        clockPaint.setColor(fgPrimary);
        String remStr = String.format(Locale.US, "%.1fs", remainingSec);
        canvas.drawText(remStr, cx - clockPaint.measureText(remStr) / 2f, cy + dp(10), clockPaint);

        textPaint.setTextSize(sp(16f));
        textPaint.setColor(fgPrimary);
        String appName = pendingGateApp.label.toUpperCase(Locale.US);
        canvas.drawText(appName, cx - textPaint.measureText(appName) / 2f, cy + dp(38), textPaint);

        // Cancel / Abort Button
        gateAbortRect.set(cx - dp(110), cy + rOuter + dp(34), cx + dp(110), cy + rOuter + dp(82));
        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(cardFill);
        canvas.drawRoundRect(gateAbortRect, dp(24), dp(24), uiPaint);
        uiPaint.setStyle(Paint.Style.STROKE);
        uiPaint.setStrokeWidth(dp(1.4f));
        uiPaint.setColor(fgPrimary);
        canvas.drawRoundRect(gateAbortRect, dp(24), dp(24), uiPaint);

        monoPaint.setTextSize(sp(11.5f));
        monoPaint.setColor(fgPrimary);
        String abortStr = "[ ABORT LAUNCH ]";
        canvas.drawText(abortStr, cx - monoPaint.measureText(abortStr) / 2f, gateAbortRect.centerY() + dp(4f), monoPaint);
    }

    // =========================================================================
    // LOCK SCREEN MAGIC (A1): LIVE HOROLOGICAL ASTROLABE WAKE OVERLAY
    // (Direct from Video 00:00 - 00:01 & 00:07)
    // =========================================================================
    private void drawWakeInstrumentOverlay(Canvas canvas, int w, int h, Calendar cal, Date nowDate, int batteryPct,
                                           long nowMs, boolean isDay, int fgPrimary, int fgSecondary, int fgMuted,
                                           int cardFill, int cardBorder) {
        // Top of Lock Screen stays clean & minimal
        String timeStr = new SimpleDateFormat("HH:mm:ss", Locale.US).format(nowDate);
        String dateStr = new SimpleDateFormat("EEE // dd MMM yyyy", Locale.US).format(nowDate).toUpperCase(Locale.US);
        monoPaint.setTextSize(sp(10f));
        monoPaint.setColor(fgSecondary);
        canvas.drawText("STANDBY.ASTROLABE // LOCK", dp(26), dp(52), monoPaint);
        canvas.drawText(dateStr, dp(26), dp(70), monoPaint);

        // Center Concentric Horological Astrolabe Rings (1..12 markers from Video 00:00)
        float cx = w * 0.5f;
        float cy = h * 0.39f;
        float r1 = dp(138);
        float r2 = dp(106);
        float r3 = dp(74);

        dialTickPaint.setStrokeWidth(dp(1.1f));
        dialTickPaint.setColor(fgSecondary);
        canvas.drawCircle(cx, cy, r1, dialTickPaint);
        canvas.drawCircle(cx, cy, r2, dialTickPaint);
        dialTickPaint.setColor(fgMuted);
        canvas.drawCircle(cx, cy, r3, dialTickPaint);

        int sec = cal.get(Calendar.SECOND);
        int min = cal.get(Calendar.MINUTE);
        int hr = cal.get(Calendar.HOUR);
        float secRot = (sec + cal.get(Calendar.MILLISECOND) / 1000f) * 6f;
        float minRot = (min + sec / 60f) * 6f;

        // 1..12 numerals around outer astrolabe ring
        monoPaint.setTextSize(sp(10f));
        monoPaint.setColor(fgPrimary);
        for (int n = 1; n <= 12; n++) {
            double rad = Math.toRadians(-90 + n * 30 + secRot * 0.15f);
            float nx = cx + (float) Math.cos(rad) * (r1 - dp(14));
            float ny = cy + (float) Math.sin(rad) * (r1 - dp(14));
            String ns = String.valueOf(n);
            canvas.drawText(ns, nx - monoPaint.measureText(ns) / 2f, ny + dp(3.5f), monoPaint);
        }

        // Sweeping astrolabe hands
        double secRad = Math.toRadians(-90 + secRot);
        double minRad = Math.toRadians(-90 + minRot);
        double hrRad = Math.toRadians(-90 + (hr + min / 60f) * 30f);

        dialTickPaint.setStrokeWidth(dp(1.8f));
        dialTickPaint.setColor(fgPrimary);
        canvas.drawLine(cx, cy, cx + (float) Math.cos(hrRad) * r3, cy + (float) Math.sin(hrRad) * r3, dialTickPaint);
        canvas.drawLine(cx, cy, cx + (float) Math.cos(minRad) * r2, cy + (float) Math.sin(minRad) * r2, dialTickPaint);
        dialTickPaint.setStrokeWidth(dp(0.9f));
        canvas.drawLine(cx, cy, cx + (float) Math.cos(secRad) * r1, cy + (float) Math.sin(secRad) * r1, dialTickPaint);

        // Center digital readout box inside astrolabe
        RectF timePill = new RectF(cx - dp(68), cy - dp(18), cx + dp(68), cy + dp(18));
        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(cardFill);
        canvas.drawRoundRect(timePill, dp(9), dp(9), uiPaint);
        uiPaint.setStyle(Paint.Style.STROKE);
        uiPaint.setStrokeWidth(dp(1.2f));
        uiPaint.setColor(fgPrimary);
        canvas.drawRoundRect(timePill, dp(9), dp(9), uiPaint);

        clockPaint.setTextSize(sp(18f));
        clockPaint.setColor(fgPrimary);
        canvas.drawText(timeStr, cx - clockPaint.measureText(timeStr) / 2f, cy + dp(6.5f), clockPaint);

        // Lower 3D Rotating Point-Cloud Sphere
        draw3DPointCloudGlobe(canvas, cx, h * 0.66f, dp(52), nowMs, fgPrimary, fgSecondary, fgMuted);

        // Bottom-Center Pill Cluster right above '[ TAP OR SWIPE TO ENGAGE ]'
        drawMicroGaugeCluster(canvas, cx, h - dp(142), batteryPct, fgPrimary, fgSecondary, fgMuted, cardFill, cardBorder);

        // Bottom Engage Hatch
        wakeUnlockRect.set(cx - dp(130), h - dp(96), cx + dp(130), h - dp(44));
        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(cardFill);
        canvas.drawRoundRect(wakeUnlockRect, dp(26), dp(26), uiPaint);
        uiPaint.setStyle(Paint.Style.STROKE);
        uiPaint.setStrokeWidth(dp(1.3f));
        uiPaint.setColor(fgPrimary);
        canvas.drawRoundRect(wakeUnlockRect, dp(26), dp(26), uiPaint);

        monoPaint.setTextSize(sp(11f));
        monoPaint.setColor(fgPrimary);
        String unlockMsg = "[ TAP OR SWIPE TO ENGAGE ]";
        canvas.drawText(unlockMsg, cx - monoPaint.measureText(unlockMsg) / 2f, wakeUnlockRect.centerY() + dp(4f), monoPaint);
    }

    private void drawBannerToast(Canvas canvas, int w, int h, int fgPrimary, int cardFill, int cardBorder) {
        monoPaint.setTextSize(sp(10f));
        float tw = monoPaint.measureText(bannerMessage);
        float padX = dp(18);
        RectF pill = new RectF((w - tw) / 2f - padX, h - dp(134), (w + tw) / 2f + padX, h - dp(104));
        uiPaint.setStyle(Paint.Style.FILL);
        uiPaint.setColor(cardFill);
        canvas.drawRoundRect(pill, dp(15), dp(15), uiPaint);
        uiPaint.setStyle(Paint.Style.STROKE);
        uiPaint.setStrokeWidth(dp(1.1f));
        uiPaint.setColor(fgPrimary);
        canvas.drawRoundRect(pill, dp(15), dp(15), uiPaint);

        monoPaint.setColor(fgPrimary);
        canvas.drawText(bannerMessage, (w - tw) / 2f, pill.centerY() + dp(3.8f), monoPaint);
    }

    // =========================================================================
    // TOUCH INTERACTION
    // =========================================================================
    @Override
    public boolean onTouchEvent(MotionEvent event) {
        float x = event.getX();
        float y = event.getY();
        int w = getWidth();
        int h = getHeight();

        // 1. If Wake Overlay is active, tapping or swiping disengages it into the launcher
        if (wakeOverlayActive) {
            if (event.getActionMasked() == MotionEvent.ACTION_UP) {
                if (wakeUnlockRect.contains(x, y) || Math.abs(y - touchStartY) > dp(40)) {
                    performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);
                    wakeOverlayActive = false;
                    invalidate();
                }
            } else if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                touchStartY = y;
            }
            return true;
        }

        // 2. If 3-Second Intention Gate is active, check abort tap
        if (pendingGateApp != null) {
            if (event.getActionMasked() == MotionEvent.ACTION_UP && gateAbortRect.contains(x, y)) {
                performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
                pendingGateApp = null;
                showBanner("LAUNCH ABORTED");
                invalidate();
            }
            return true;
        }

        float railTop = dp(335);
        float railBottom = h - dp(104);

        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN: {
                touchStartX = x;
                touchStartY = y;
                lastTouchY = y;
                isDraggingList = false;
                longPressTriggered = false;
                pressedAppIndex = -1;
                pressedDockIndex = -1;

                // Right-edge A-Z Vernier Rail
                if (x >= w - dp(44) && y >= railTop && y <= railBottom) {
                    isScrubbingRail = true;
                    updateRailScrub(y, railTop, railBottom);
                    invalidate();
                    return true;
                }

                // Bottom 5-Tool Dock
                for (int i = 0; i < 5; i++) {
                    if (dockSlotRects[i].contains(x, y)) {
                        pressedDockIndex = i;
                        invalidate();
                        return true;
                    }
                }

                // 3D Drum App Rows
                for (int i = 0; i < appRowRects.size(); i++) {
                    if (appRowRects.get(i).contains(x, y)) {
                        pressedAppIndex = i;
                        postDelayed(longPressRunnable, 480L);
                        invalidate();
                        break;
                    }
                }
                return true;
            }

            case MotionEvent.ACTION_MOVE: {
                if (isScrubbingRail) {
                    updateRailScrub(y, railTop, railBottom);
                    invalidate();
                    return true;
                }

                float dy = y - lastTouchY;
                if (Math.abs(y - touchStartY) > dp(10) || Math.abs(x - touchStartX) > dp(10)) {
                    removeCallbacks(longPressRunnable);
                    pressedAppIndex = -1;
                    pressedDockIndex = -1;
                    if (maxScrollY > 0f) {
                        isDraggingList = true;
                        scrollOffsetY -= dy;
                        if (scrollOffsetY < 0f) scrollOffsetY = 0f;
                        if (scrollOffsetY > maxScrollY) scrollOffsetY = maxScrollY;
                    }
                    invalidate();
                }
                lastTouchY = y;
                return true;
            }

            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL: {
                removeCallbacks(longPressRunnable);
                if (isScrubbingRail) {
                    isScrubbingRail = false;
                    scrubY = -1f;
                    lastScrubIndex = -1;
                    invalidate();
                    return true;
                }

                int tappedApp = pressedAppIndex;
                int tappedDock = pressedDockIndex;
                pressedAppIndex = -1;
                pressedDockIndex = -1;

                if (!isDraggingList && !longPressTriggered && event.getActionMasked() == MotionEvent.ACTION_UP) {
                    handleTap(x, y, tappedApp, tappedDock);
                }
                isDraggingList = false;
                invalidate();
                return true;
            }
        }
        return super.onTouchEvent(event);
    }

    private void updateRailScrub(float y, float railTop, float railBottom) {
        scrubY = y;
        float norm = (y - railTop) / (railBottom - railTop);
        int idx = Math.max(0, Math.min(RAIL_CHARS.length() - 1, Math.round(norm * (RAIL_CHARS.length() - 1))));
        if (idx != lastScrubIndex) {
            lastScrubIndex = idx;
            activeFilterChar = RAIL_CHARS.charAt(idx);
            scrollOffsetY = 0f;
            rebuildVisibleApps();
            performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
        }
    }

    private void handleTap(float x, float y, int tappedApp, int tappedDock) {
        // 1. Top-Right Device Micro-Gauge -> Engage Horological Standby Lock Overlay
        if (gaugeDeviceRect.contains(x, y)) {
            performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
            wakeOverlayActive = true;
            return;
        }

        // 2. Bottom 5-Tool Dock -> 0ms Instant Launch (PhonePe, Gmail, WhatsApp, Brave, Maps)
        if (tappedDock >= 0 && tappedDock < 5) {
            performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);
            launchPackageImmediate(DOCK_PACKAGES[tappedDock], DOCK_LABELS[tappedDock]);
            return;
        }

        // 3. Tapped an App in the 3D Drum
        if (tappedApp >= 0 && tappedApp < visibleApps.size()) {
            performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);
            AppEntry app = visibleApps.get(tappedApp);
            if (app.isActionRow || app.isPrivateSpace || isZeroFrictionUtility(app.packageName)) {
                launchAppImmediate(app);
            } else {
                // Innovation 5: Trigger 3-Second Intention Gate
                pendingGateApp = app;
                gateStartMs = SystemClock.uptimeMillis();
            }
            return;
        }

        // 4. Double-Tap QUANTUM.CORE Header -> Toggle Day E-Ink Preview vs Auto/Night
        if (quantumHeaderRect.contains(x, y)) {
            long now = SystemClock.uptimeMillis();
            if (now - lastCoreTapMs < 380L) {
                lastCoreTapMs = 0L;
                boolean currentlyDay = isDayModeActive(Calendar.getInstance());
                setDayNightOverride(currentlyDay ? "night" : "day");
            } else {
                lastCoreTapMs = now;
            }
            return;
        }

        // 5. Tapping outside while filtered returns to Favorites
        if (activeFilterChar != '☆') {
            resetToFavorites();
            return;
        }

        // 6. Double-Tap empty dial area -> Toggle Wireframe Icons vs Pure Text on the 3D Drum
        long now = SystemClock.uptimeMillis();
        if (now - lastCoreTapMs < 360L) {
            lastCoreTapMs = 0L;
            setLayoutMode((layoutMode == 2) ? 0 : 2);
        } else {
            lastCoreTapMs = now;
        }
    }

    private void launchAppImmediate(AppEntry app) {
        if (app == null) return;
        if (app.isActionRow) {
            togglePrivateSpaceLock(!"__private_lock__".equals(app.packageName));
            return;
        }
        if (app.componentName != null && app.userHandle != null) {
            try {
                LauncherApps la = (LauncherApps) getContext().getSystemService(Context.LAUNCHER_APPS_SERVICE);
                if (la != null) {
                    la.startMainActivity(app.componentName, app.userHandle, null, null);
                    return;
                }
            } catch (Throwable t) {
                Toast.makeText(getContext(), "Unable to open " + app.label, Toast.LENGTH_SHORT).show();
                return;
            }
        }
        launchPackageImmediate(app.packageName, app.label);
    }

    private void togglePrivateSpaceLock(boolean unlock) {
        try {
            UserManager um = (UserManager) getContext().getSystemService(Context.USER_SERVICE);
            if (um == null) return;
            UserHandle target = privateProfileHandle;
            if (target == null) {
                UserHandle me = Process.myUserHandle();
                for (UserHandle u : um.getUserProfiles()) {
                    if (!me.equals(u)) {
                        target = u;
                        privateProfileHandle = u;
                        break;
                    }
                }
            }
            if (target != null && Build.VERSION.SDK_INT >= 28) {
                um.requestQuietModeEnabled(!unlock, target);
                showBanner(unlock ? "UNLOCKING PRIVATE SPACE" : "LOCKING PRIVATE SPACE");
                postDelayed(new Runnable() {
                    @Override
                    public void run() {
                        reloadInstalledApps();
                        invalidate();
                    }
                }, 800L);
            } else {
                Toast.makeText(getContext(), "Private Space profile not found", Toast.LENGTH_SHORT).show();
            }
        } catch (Throwable t) {
            Toast.makeText(getContext(), "Private Space toggle failed", Toast.LENGTH_SHORT).show();
        }
    }

    private void launchPackageImmediate(String pkg, String label) {
        try {
            Intent launch = getContext().getPackageManager().getLaunchIntentForPackage(pkg);
            if (launch != null) {
                launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                getContext().startActivity(launch);
            } else {
                Toast.makeText(getContext(), label + " is not installed", Toast.LENGTH_SHORT).show();
            }
        } catch (Throwable t) {
            Toast.makeText(getContext(), "Unable to open " + label, Toast.LENGTH_SHORT).show();
        }
    }
}
