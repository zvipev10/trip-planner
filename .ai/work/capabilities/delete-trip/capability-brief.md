# Delete existing trips

User requested a small elegant delete icon. Scope: Android and web saved-trip lists. Keep trip opening separate from deletion, use a restrained 20dp outline trash icon inside a 48dp tap target, and confirm the named trip with a clear warning that locations and saved route are removed. Cancel leaves data unchanged. Other trips remain intact. No schema/API change; Android already has cascading location deletion. iOS parity is outside this slice.

Developer/UX/QA review: use existing write/error paths, delete by immutable ID, disable while saving, preserve pending shares. Verify cancellation, deletion persistence, unaffected other trips, and Android foreign-key cascade. No new dependency.

Execution: (1) add Android DAO/ViewModel/delete confirmation and web list icon reusing deletion; (2) validate build/lint and browser interactions; (3) publish PR, versioned APK and handoff. User's explicit implementation request authorizes this focused behavior change; physical phone acceptance remains manual.
