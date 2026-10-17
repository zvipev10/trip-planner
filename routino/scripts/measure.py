"""Execute a subprocess and record wall time, peak RSS and observed disk footprint.

Linux wait4 reports process RSS; this is not whole-VM or cgroup memory use.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('--result', required=True)
parser.add_argument('--log', required=True)
parser.add_argument('--watch-dir', required=True)
parser.add_argument('--memory-mib', type=int)
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ['--'] else args.command

def footprint():
    total = 0
    for root, _, files in os.walk(args.watch_dir):
        for name in files:
            try:
                total += os.stat(os.path.join(root, name)).st_size
            except FileNotFoundError:
                pass
    return total

def limit():
    if args.memory_mib:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (args.memory_mib * 1024**2,) * 2)

started = time.monotonic()
peak_disk = footprint()
with open(args.log, 'wb') as log:
    child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, preexec_fn=limit)
    while True:
        pid, status, usage = os.wait4(child.pid, os.WNOHANG)
        peak_disk = max(peak_disk, footprint())
        if pid:
            child.returncode = os.waitstatus_to_exitcode(status)
            break
        time.sleep(0.01)
result = dict(command=command, exitCode=child.returncode, wallSeconds=round(time.monotonic()-started, 3), peakRssMiB=round(usage.ru_maxrss/1024, 2), peakObservedDiskMiB=round(peak_disk/1024**2, 2), finalDiskMiB=round(footprint()/1024**2, 2), addressSpaceLimitMiB=args.memory_mib)
Path(args.result).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
raise SystemExit(child.returncode)
