"""Loopback-only UI and JSON instrument receiver. Never publishes observations."""
from datetime import datetime,timezone,timedelta
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit
import uuid
from .catalog import load_catalog,fetch_catalog,utc
from .orbit import Observer,grid,predict,pass_events
from .observations import associate,track_observations
from .storage import Store,parse_csv
from .report import write_report
from .bluetooth import BluetoothCapture,ports

class Application:
    def __init__(self,catalog_path,runtime,example_path=None):
        self.catalog_path=Path(catalog_path).resolve();self.catalog=load_catalog(catalog_path)
        self.runtime=Path(runtime).resolve();self.runtime.mkdir(parents=True,exist_ok=True)
        self.store=Store(self.runtime/'measurements.sqlite');self.lock=threading.Lock()
        token_path=self.runtime/'instrument-token.txt'
        if not token_path.exists():token_path.write_text(secrets.token_urlsafe(32),encoding='utf-8')
        self.token=token_path.read_text(encoding='utf-8').strip();self.example_path=example_path
        self.capture=BluetoothCapture(self.store)
    def analyze(self,session_id):
        session=self.store.read(session_id);station=Observer(**session['station']);rows=session['observations']
        with self.lock:catalog=list(self.catalog)
        result=associate(catalog,rows,station)
        out={'session_id':session_id,'source':session['source'],'association':result}
        if session['source']=='bluetooth-lx200-pointing':
            out['notice']='Odczyt kierunku teleskopu; dopasowanie wskazuje kandydata w tym kierunku, nie potwierdza detekcji obiektu.'
        if result['status']=='matched':
            row=next(r for r in catalog if int(r['NORAD_CAT_ID'])==result['norad_id'])
            out['tracking']=track_observations(row,rows,station)
        directory=self.runtime/'sessions'/session_id;directory.mkdir(parents=True,exist_ok=True)
        (directory/'analysis.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
        return out
    def forecast(self,body):
        observer=Observer(**body['station']);start=utc(body['start'])
        hours=float(body.get('hours',3));times=grid(start,hours,30)
        with self.lock:catalog=list(self.catalog)
        objects=[]
        for row in catalog:
            obj=predict(row,times,observer)
            obj['pass_events']=pass_events(row,start,start+timedelta(hours=24),observer)
            objects.append(obj)
        payload={'model':'SGP4 / Skyfield','version':'0.1.0','generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'observer':asdict(observer),'catalog_sha256':hashlib.sha256(json.dumps(catalog,sort_keys=True).encode()).hexdigest(),
            'minimum_pass_elevation_deg':10,'pass_window_hours':24,'objects':objects}
        name=str(uuid.uuid4());dest=self.runtime/'reports'/name;dest.mkdir(parents=True)
        write_report(payload,dest/'dashboard.html')
        (dest/'prediction.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
        return {'report_url':f'/reports/{name}/dashboard.html','json_url':f'/reports/{name}/prediction.json'}
    def refresh(self):
        with self.lock:
            ids=[int(r['NORAD_CAT_ID']) for r in self.catalog]
            path=self.runtime/'catalogs'/('catalog_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:6]+'.json')
            catalog=fetch_catalog(ids,path)
            self.catalog=catalog;self.catalog_path=path
        return {'objects':len(catalog),'epochs':[r['EPOCH'] for r in catalog]}

def make_server(app,port=8766):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,value,content_type='application/json; charset=utf-8'):
            payload=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        def permitted(self,write=False):
            allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in allowed:return False
            origin=self.headers.get('Origin')
            if origin and origin not in {'http://'+a for a in allowed}:return False
            if write and not secrets.compare_digest(self.headers.get('X-TIMDR-Key',''),app.token):return False
            return True
        def do_GET(self):
            if not self.permitted():self.respond(403,{'error':'Niedozwolony host lub origin'});return
            path=urlsplit(self.path).path
            try:
                if path=='/':
                    self.respond(200,Path(__file__).with_name('console.html').read_bytes(),'text/html; charset=utf-8')
                elif path=='/api/config':
                    self.respond(200,{'key':app.token,'catalog':[{'id':int(r['NORAD_CAT_ID']),'name':r['OBJECT_NAME'],'epoch':r['EPOCH']} for r in app.catalog],
                        'database_path':str(app.store.path),'now_utc':datetime.now(timezone.utc).isoformat()})
                elif path=='/api/sessions':self.respond(200,app.store.sessions())
                elif path=='/api/bluetooth/ports':self.respond(200,ports())
                elif path=='/api/bluetooth/status':self.respond(200,app.capture.status())
                elif path=='/api/example':
                    if app.example_path is None:raise ValueError('Przykład nie jest dostępny')
                    self.respond(200,{'station':{'latitude_deg':52.2297,'longitude_deg':21.0122,'elevation_m':110},
                        'source':'synthetic-demo','observations':parse_csv(Path(app.example_path).read_text(encoding='utf-8'))})
                elif path.startswith('/reports/'):
                    parts=path.split('/')
                    if len(parts)!=4 or parts[3] not in ('dashboard.html','prediction.json'):raise ValueError('Niepoprawna ścieżka raportu')
                    ident=str(uuid.UUID(parts[2]));file=app.runtime/'reports'/ident/parts[3]
                    mime='text/html; charset=utf-8' if file.suffix=='.html' else 'application/json; charset=utf-8'
                    self.respond(200,file.read_bytes(),mime)
                else:self.respond(404,{'error':'Nie znaleziono'})
            except (ValueError,OSError) as exc:self.respond(400,{'error':str(exc)})
        def do_POST(self):
            if not self.permitted(write=True):self.respond(403,{'error':'Niepoprawny klucz API, host lub origin'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=2_000_000:raise ValueError('Rozmiar żądania musi wynosić 1..2000000 bajtów')
                body=json.loads(self.rfile.read(length));path=urlsplit(self.path).path
                if path in ('/api/measurements','/api/import-csv'):
                    rows=parse_csv(body['csv']) if path.endswith('import-csv') else body['observations']
                    result=app.store.ingest(rows,body['station'],body.get('source','csv' if path.endswith('import-csv') else 'instrument'),body.get('session_id'))
                elif path=='/api/analyze':result=app.analyze(body['session_id'])
                elif path=='/api/predict':result=app.forecast(body)
                elif path=='/api/refresh':result=app.refresh()
                elif path=='/api/bluetooth/start':result=app.capture.start(body['port'],body['station'],int(body.get('baudrate',9600)),float(body.get('interval_s',1)))
                elif path=='/api/bluetooth/stop':result=app.capture.stop()
                else:self.respond(404,{'error':'Nie znaleziono'});return
                self.respond(200,result)
            except (ValueError,KeyError,TypeError,OSError) as exc:self.respond(400,{'error':str(exc)})
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)

def serve(catalog_path,runtime='runtime',port=8766,example_path=None):
    app=Application(catalog_path,runtime,example_path);server=make_server(app,port)
    print(f'TIMDR: http://127.0.0.1:{server.server_port}',flush=True)
    print(f'Baza pomiarów: {app.store.path}',flush=True)
    print(f'Klucz urządzenia: {app.runtime / "instrument-token.txt"}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:app.capture.stop();server.server_close()
