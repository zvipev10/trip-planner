# Repeatable comparison
Use backend's virtualenv and an exported private RouteRequest payload:

```powershell
python tools/compare_valhalla.py C:/private/route.json --base-url https://valhalla1.openstreetmap.de > C:/private/strict-result.json
python tools/compare_valhalla.py C:/private/route.json --base-url https://valhalla1.openstreetmap.de --allow-unpaved > C:/private/unpaved-result.json
```

Each invocation performs one ordered-route request, never optimizes/reorders stops or changes app data/provider. Results include route geometry for inspecting snapping. Demo server is for occasional evaluation only; do not configure production traffic or automatic fallback to it. Allow-unpaved is explicit and only affects this invocation. For sustained testing, use a dedicated Valhalla deployment and validate full matrix/route semantics before integration. The live VM lacks comfortable memory headroom for an additional engine build/service.
