# Android build validation — 2026-10-17

Verified source commit: `8b15c0fe4588b5b096af18ed23d462df1996a8c8`.

GitHub Actions run:
https://github.com/zvipev10/trip-planner/actions/runs/39047260207

The Ubuntu runner used JDK 17 and the checked-in Gradle 8.11.1 wrapper. The
following tasks completed successfully:

```text
:app:assembleDebug
:app:testDebugUnitTest
:app:lintDebug
```

The `trip-planner-debug` artifact contains `app-debug.apk` and is retained for
seven days (currently expires 2026-10-24). Download:
https://github.com/zvipev10/trip-planner/actions/runs/39047260207/artifacts/12106685407

Eight JVM test cases cover Waze encoded coordinate queries, Google Maps explicit
queries, shared labels/links, pasted coordinates, camera-position rejection,
unresolved links/addresses, malformed and out-of-range coordinates, and Hebrew
labels. This is not a live Google Maps/Waze place-resolution integration test.

The save dialogs now close only after successful persistence, keeping edits
available on failure. Room excludes the computed resolved-state property from
the stored schema. A new Android CI job builds, tests, lints and uploads the APK.
The backend workflow also passed on the same commit.

No emulator or phone run has been performed. Database persistence across app
restarts, Hebrew/RTL layout, UI interaction and Android share-sheet behavior
still require device testing. Automatic address/short-link resolution, route
optimization integration, route maps and manual route reordering are not wired
into Android yet. The APK currently supports collecting local trips/locations
and selecting endpoints, with routing clearly marked as unavailable.

The build is debug-signed, not a production release. Upstream action deprecation
warnings appeared but did not fail build/test/lint. Local builds in the managed
workspace were blocked by toolchain/network constraints; successful compilation
was established on GitHub's runner instead.
