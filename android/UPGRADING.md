# Android upgrades without trip loss

## Normal upgrades after the signing transition

Install the newer APK over the existing application; do not uninstall or clear data. Keep applicationId `com.tripplanner`, use the permanent signing certificate, and increment versionCode. Room uses `trips.db` and explicit migrations; do not add destructive migration fallbacks. Endpoints, trips, locations and saved routes stay in app-private storage.

CI uses encrypted repository secrets `TRIP_SIGNING_STORE_BASE64` and `TRIP_SIGNING_PASSWORD`. The keystore alias is `tripplanner`. A private recovery copy is under `/home/ubuntu/.config/trip-planner-signing/` on the VM (owner-only access). Never commit keystores, passwords or private trip backups. Back up the signing identity to another secure administrator-controlled location. Losing this identity prevents future in-place updates.

Main builds fail if signing secrets are absent. Fork PR builds use temporary debug identities and must never be distributed as upgrades. Each distributable CI artifact includes its signing certificate fingerprint; compare fingerprints before publishing. These remain debug builds, not a Play Store release process.

## One-time transition from 0.5.1 and earlier CI debug builds

Earlier runners generated independent debug keys and retained only APKs. The old private signing keys cannot be recovered from APK certificates. The new permanent identity cannot update those installations in place. **Do not uninstall the existing app or clear its data before making a verified backup.**

Use a USB-connected computer with official Android platform-tools, USB debugging and authorization on the phone. Version 0.5.1 is debuggable, so `adb run-as` can access its database without rooting. Only one device should be connected.

1. Leave 0.5.1 installed. Run `python tools/android_trip_backup.py backup trips-before-signing-change.tar`. The script stops the app, copies the database with its SQLite sidecars, validates integrity, and prints trip/place counts. It never uninstalls the app. Keep the archive private and keep an extra copy.
2. Only after the backup succeeds and the counts match, arrange the one-time application replacement on the phone. Do not remove the old app until a recovery copy exists.
3. Install the permanently signed build and open it once, then close it.
4. Restore using `python tools/android_trip_backup.py restore trips-before-signing-change.tar --replace-database`. Restore replaces the new installation's local database. Do not add new trips before restoration; they would be replaced.
5. Open the app and verify all trip names, locations, endpoints and saved routes. Keep the backup until verified.

The backup/restore utility operates locally over adb; it does not upload trips. Installation, USB pairing and physical-device verification require the user's phone. The one-time transition has not been exercised on the user's phone.
