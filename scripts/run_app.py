"""Start the local observation UI and Bluetooth receiver."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import webbrowser
root=Path(__file__).resolve().parents[1]
python=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if not python.exists():subprocess.run([sys.executable,'-m','venv',str(root/'.venv')],check=True)
probe=subprocess.run([str(python),'-c','import skyfield,sgp4,numpy,scipy,jplephem,serial'],capture_output=True)
if probe.returncode:subprocess.run([str(python),'-m','pip','install','-e',str(root)],check=True)
# Open once; server startup is usually faster than a browser launch.
timer=threading.Timer(2.,lambda:webbrowser.open('http://127.0.0.1:8766/'));timer.daemon=True;timer.start()
subprocess.run([str(python),'-m','timdr_orbit.cli','serve','--catalog','data/catalog_2026-09-28.json',
    '--example','artifacts/validation/synthetic_observations.csv'],cwd=root,check=True)
