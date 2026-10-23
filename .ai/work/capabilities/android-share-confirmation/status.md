# Status

Android 0.5.4/code 10 published; fix merged in PR #21. Owner: user for physical-device acceptance.

- Android assembleDebug, testDebugUnitTest and lintDebug passed in run 39938314980 on commit 9e422e5.
- Backend and web CI passed.
- APK signing SHA256 matches permanent release identity: a4a95b4d19020c11527e28572587b51f293d42c16e956722be5e9c56c3532272.
- Public APK downloaded and SHA256 verified: daa9cfc08356d8b1188e14a709fbe36dcbed6d217d0f4bdeb631d987803206ab.
- Download: http://151.145.93.180/trip-planner/web/downloads/trip-planner-0.5.4.apk
- Next: install over 0.5.3 without uninstalling; confirm trips remain, share a place, confirm notification disappears and navigation clears it.
- Limitation: physical Android device acceptance not performed here. No database migration, backend restart or architecture doc update required.
