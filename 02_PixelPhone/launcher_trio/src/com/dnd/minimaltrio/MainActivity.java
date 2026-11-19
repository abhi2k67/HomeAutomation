package com.dnd.minimaltrio;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;

public class MainActivity extends Activity {
    private LauncherView launcherView;

    private final BroadcastReceiver screenReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (intent == null || launcherView == null) return;
            String action = intent.getAction();
            if (Intent.ACTION_SCREEN_OFF.equals(action)) {
                launcherView.onScreenTurnedOff();
            } else if (Intent.ACTION_USER_PRESENT.equals(action) || Intent.ACTION_SCREEN_ON.equals(action)) {
                launcherView.onScreenWoke();
            } else {
                launcherView.onHostResume();
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureEdgeToEdge();
        launcherView = new LauncherView(this);
        setContentView(launcherView);

        IntentFilter filter = new IntentFilter();
        filter.addAction(Intent.ACTION_SCREEN_OFF);
        filter.addAction(Intent.ACTION_SCREEN_ON);
        filter.addAction(Intent.ACTION_USER_PRESENT);
        filter.addAction("android.intent.action.PROFILE_AVAILABLE");
        filter.addAction("android.intent.action.PROFILE_UNAVAILABLE");
        registerReceiver(screenReceiver, filter);

        handleCommandIntent(getIntent());
    }

    @Override
    protected void onDestroy() {
        try {
            unregisterReceiver(screenReceiver);
        } catch (Throwable ignored) {
        }
        super.onDestroy();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (launcherView != null) {
            launcherView.resetToFavorites();
            handleCommandIntent(intent);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        configureEdgeToEdge();
        if (launcherView != null) {
            launcherView.onHostResume();
        }
    }

    @Override
    public void onBackPressed() {
        if (launcherView != null) {
            if (launcherView.cancelActiveGateOrOverlay()) {
                return;
            }
            if (launcherView.isFiltered()) {
                launcherView.resetToFavorites();
            }
        }
    }

    private void handleCommandIntent(Intent intent) {
        if (intent == null || launcherView == null) return;
        if (intent.hasExtra("mode")) {
            String m = intent.getStringExtra("mode");
            launcherView.setDayNightOverride(m);
        }
        if (intent.hasExtra("wake")) {
            boolean w = intent.getBooleanExtra("wake", false);
            launcherView.setWakeOverlayActive(w);
        }
        if (intent.hasExtra("layout")) {
            int l = intent.getIntExtra("layout", -1);
            if (l >= 0 && l <= 2) {
                launcherView.setLayoutMode(l);
            }
        }
    }

    @SuppressWarnings("deprecation")
    private void configureEdgeToEdge() {
        Window w = getWindow();
        if (w == null) return;
        w.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
        w.setStatusBarColor(Color.TRANSPARENT);
        w.setNavigationBarColor(Color.TRANSPARENT);
        if (Build.VERSION.SDK_INT >= 28) {
            WindowManager.LayoutParams lp = w.getAttributes();
            lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            w.setAttributes(lp);
        }
        if (Build.VERSION.SDK_INT >= 29) {
            w.setNavigationBarContrastEnforced(false);
            w.setStatusBarContrastEnforced(false);
        }
        if (Build.VERSION.SDK_INT >= 30) {
            w.setDecorFitsSystemWindows(false);
            WindowInsetsController ctrl = w.getInsetsController();
            if (ctrl != null) {
                ctrl.hide(WindowInsets.Type.statusBars());
                ctrl.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            View decor = w.getDecorView();
            decor.setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            );
        }
    }
}
