# Stride for Android

A thin Android shell around the web app in `../stride`. It adds the one thing a browser
cannot do: reading your step count from Health Connect.

## How it fits together

```
Google Fit / watch app ──writes──▶ Health Connect ──reads──▶ HealthBridge.kt
                                                                  │
                    stride/js/native.js ◀── JS bridge ── MainActivity.kt (WebView)
```

- The web files are copied from `../stride` into the APK at build time. There is one copy of the app.
- The shell asks for a single permission: read steps. It never writes to Health Connect.
- Steps are read when the app opens, when you come back to it, and when you change day.
  A day whose steps you typed by hand is left alone until you tap "Use Health Connect".
- App data lives in the WebView's storage on the phone. Use "Export backup" before uninstalling.

## Build

Needs JDK 17+ and the Android SDK (platform 36, build-tools 36).

```sh
export ANDROID_HOME=/path/to/android-sdk
./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

`sideload.keystore` is a fixed signing key (password `android`) so that every build can
update the installed app without wiping its data. It is for personal sideloading only;
replace it with a private key before publishing the app anywhere.

## On the phone

1. Install Google Fit and turn on Health Connect sync in its settings.
   Any app that writes steps to Health Connect works.
2. Install the APK and open Stride.
3. On the Today screen tap "Connect Health Connect" and allow Steps.

## Status

Compiles, passes lint and unit tests, and the web side is tested against a simulated bridge.
It has not been run on a physical phone or an emulator yet.
