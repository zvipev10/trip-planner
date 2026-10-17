"""Run measured shortest/quickest CLI samples against the imported road graph."""
import json
from pathlib import Path
import subprocess
import sys

base = Path(__file__).resolve().parents[1]
vendor = base / 'vendor/routino-3.4.4'
scenarios = {
    'tel-aviv-local': ((32.080, 34.780), (32.060, 34.770)),
    'tel-aviv-jerusalem': ((32.080, 34.780), (31.780, 35.220)),
    'haifa-local': ((32.815, 34.990), (32.790, 34.970)),
    'beer-sheva-mitzpe-ramon': ((31.250, 34.790), (30.610, 34.800)),
}
results = []
for name, (start, end) in scenarios.items():
    for mode in ('shortest', 'quickest'):
        output = base / 'runs' / f'{name}-{mode}'
        output.mkdir(exist_ok=True)
        command = [str(vendor/'src/router-slim'), f'--dir={base / "data/israel"}', f'--profiles={base / "profiles/distance-car.xml"}', f'--translations={vendor / "xml/routino-translations.xml"}', '--profile=distance-car', f'--{mode}', f'--lat1={start[0]}', f'--lon1={start[1]}', f'--lat2={end[0]}', f'--lon2={end[1]}', '--output-text-all', '--output-gpx-track', '--quiet']
        measured = subprocess.run([sys.executable, str(base/'scripts/measure.py'), '--result', str(output/'measurement.json'), '--log', str(output/'router.log'), '--watch-dir', str(output), '--memory-mib', '128', '--', *command], cwd=output, capture_output=True, text=True, timeout=90)
        record = json.loads((output/'measurement.json').read_text())
        record.update(scenario=name, mode=mode)
        if record['exitCode'] == 0:
            rows = [line.split('\t') for line in (output/f'{mode}-all.txt').read_text().splitlines() if line and not line.startswith('#')]
            record['distanceKmRoundedTo10m'] = float(rows[-1][6])
            record['geometryRows'] = len(rows)
        else:
            record['failure'] = (output/'router.log').read_text()[-500:]
        results.append(record)
        print(json.dumps({k: v for k,v in record.items() if k != 'command'}), flush=True)
(base/'runs/route-summary.json').write_text(json.dumps(results, indent=2)+'\n')
if any(r['exitCode'] != 0 for r in results):
    raise SystemExit(1)
