# Schimmelpilz für Android

Native App (Kotlin, Jetpack Compose) für den Schimmelpilz-Server. Sie startet mit dem
Assistenten und bietet unterwegs die Kernfunktionen der Web-App: Akten, Fragen zu einer Akte
mit Gesetzesquellen, Posteingang mit Dokumentenscanner, Fristen und Aufgaben.
Registrierung, Abo-Verwaltung und die übrigen Kanzlei-Module öffnen die Web-App im Browser.

Die App spricht dieselbe API wie die Web-App (Session-Cookie plus Header
`X-Schimmelpilz-Request: 1`). Ein eigener Backend-Teil ist nicht nötig.

## Voraussetzungen

- JDK 17
- Android SDK mit Plattform 36 (`ANDROID_HOME` oder `local.properties` mit `sdk.dir=…`)

## Bauen

```sh
./gradlew :app:assembleDebug          # Debug-APK, Server http://10.0.2.2:8001/ (Emulator → Host)
./gradlew :app:testDebugUnitTest      # Unit-Tests
./gradlew :app:lintDebug
```

Andere Server-Adresse für Debug-Builds: `-PdebugApiUrl=http://192.168.1.20:8001/` oder
`SCHIMMELPILZ_DEBUG_API_URL`. Debug-Builds erlauben unverschlüsseltes HTTP nur zu
`10.0.2.2`, `localhost` und `127.0.0.1`.

## Auf einem Handy testen (z. B. Pixel 6)

1. Test-APK bauen: `./gradlew :app:assembleDebug` → `app/build/outputs/apk/debug/app-debug.apk`.
2. Server im Heimnetz erreichbar starten, auf dem PC im Projektordner:
   `python -m uvicorn server.app:app --host 0.0.0.0 --port 8001`
   (Windows-Firewall für Port 8001 im privaten Netz erlauben). Konto vorher in der Web-App anlegen.
   Für die Texterkennung von Fotos und Scans einmalig: `npm install --prefix server/ocr` und
   `node server/ocr/setup-models.mjs data/ocr-models` (im Docker-Image ist das schon enthalten).
3. APK aufs Handy kopieren und öffnen; Installation aus dieser Quelle einmalig erlauben.
4. In der App auf „Los geht’s“, unten bei „Server“ auf „Ändern“ und die PC-Adresse eintragen,
   z. B. `192.168.1.20:8001` (IP unter Windows mit `ipconfig`). Dann anmelden.

Die Server-Adresse lässt sich in jeder Version auf der Anmeldeseite ändern. Test-Builds erlauben dafür
unverschlüsseltes HTTP; Release-Builds nur HTTPS.


Release-Builds sprechen nur HTTPS. Die Server-Adresse immer angeben (ohne Angabe steht dort der Platzhalter `https://example.com/`):

```sh
./gradlew :app:bundleRelease -PapiUrl=https://kanzlei.example.de/
```

Signatur: `keystore.properties` im Ordner `android/` anlegen (wird nicht eingecheckt) mit

```
storeFile=/pfad/zu/upload.jks
storePassword=…
keyAlias=upload
keyPassword=…
```

oder die Umgebungsvariablen `SCHIMMELPILZ_KEYSTORE`, `SCHIMMELPILZ_KEYSTORE_PASSWORD`,
`SCHIMMELPILZ_KEY_ALIAS`, `SCHIMMELPILZ_KEY_PASSWORD` setzen. Für Google Play die
Play App Signing nutzen und nur den Upload-Schlüssel lokal halten.

## Screenshots

`ScreenshotTest` geht die App gegen einen laufenden Server durch und speichert ein PNG pro
Screen (Robolectric, kein Emulator nötig). Ohne `-Pscreenshots` wird der Test übersprungen.

```sh
SCHIMMELPILZ_DEBUG_API_URL=http://127.0.0.1:8001/ ./gradlew :app:testDebugUnitTest \
  --tests '*ScreenshotTest*' -Pscreenshots=/tmp/screens \
  -Pdemo.email=kanzlei@example.invalid -Pdemo.password=…
```

Erwartet ein Demo-Konto mit der Akte „Mietminderung Heizungsausfall“ und einer
abgeschlossenen Recherche. Dialoge mit Textfeldern werden unter Robolectric nie „idle“
und sind deshalb nicht Teil des Durchgangs.

## Vor der Veröffentlichung im Play Store

- Logo: Gesamt-Logo (`res/drawable-nodpi/logo_full.webp`) und Bildmarke (`logo_mark.webp`, auch App-Symbol
  und `store/icon-512.png`) stammen aus der Logo-Datei (2000 × 781 px). Bei einer neuen Fassung alle drei
  sowie `res/mipmap-*/ic_launcher_foreground.webp` daraus neu erzeugen.

- Abos: Käufe in der App müssten über Google Play Billing laufen. Die App verkauft daher
  nichts selbst und verweist für Abos auf die Web-App; vor einem In-App-Verkauf Play
  Billing anbinden und die Server-Abrechnung erweitern.
- Store-Eintrag: Texte, Grafiken und die Vorlage für „Datensicherheit“ liegen in `store/` (siehe `store/README.md`).
- Kontolöschung: in der App unter Mehr → Konto löschen, im Web unter Kanzlei / Profil.

Schrift: Plus Jakarta Sans (SIL Open Font License, siehe `licenses/`).
