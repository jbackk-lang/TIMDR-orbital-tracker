import json
from pathlib import Path

def write_report(payload,path):
    template=Path(__file__).with_name('dashboard.html').read_text(encoding='utf-8')
    # Prevent a catalog name from closing the embedded application/json script.
    content=json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    Path(path).write_text(template.replace('__PAYLOAD__',content),encoding='utf-8')
