"""One-command local setup and reproducible demo; no global package changes."""
import os
from pathlib import Path
import subprocess
import sys
import webbrowser

root=Path(__file__).resolve().parents[1]
python=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if not python.exists():subprocess.run([sys.executable,'-m','venv',str(root/'.venv')],check=True)
probe=subprocess.run([str(python),'-c','import skyfield,sgp4,numpy,scipy,jplephem'],capture_output=True)
if probe.returncode:subprocess.run([str(python),'-m','pip','install','-e',str(root)],check=True)
subprocess.run([str(python),'-m','timdr_orbit.cli','predict','--catalog','data/catalog_2026-09-28.json',
    '--lat','52.2297','--lon','21.0122','--height','110','--start','2026-09-28T20:00:00Z',
    '--hours','3','--pass-hours','24','--step','30','--out','artifacts/demo'],cwd=root,check=True)
path=root/'artifacts/demo/dashboard.html'
print('Zapisano:',path)
webbrowser.open(path.as_uri())
