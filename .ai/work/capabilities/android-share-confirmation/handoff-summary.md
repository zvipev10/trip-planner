# Android 0.5.4: transient share confirmation

Goal: remove stale share confirmations; produce an install-over upgrade.
Root cause: ViewModel status rendered globally without expiry or navigation cleanup.
Fix: short dismissible Material3 snackbar, cleared on navigation, share dismissal and completion. Conditional cleanup preserves different newer messages. Progress remains in share card.
Version 0.5.4/code 10; package, Room schema and permanent signing identity unchanged.
QA: CI assembly/unit tests/lint required before distribution. Physical device install-over and share/navigation remain user acceptance steps.
Scope: Android only. No backend/database changes or architecture documentation updates needed.
