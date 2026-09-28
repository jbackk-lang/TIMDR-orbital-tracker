"""Local measurement sessions. Runtime data is excluded from version control."""
from datetime import datetime,timezone
import csv
import io
import math
import sqlite3
import uuid
from dataclasses import asdict
from pathlib import Path
from contextlib import contextmanager
from .catalog import utc
from .orbit import Observer

def parse_csv(text):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required={'time_utc','azimuth_deg','elevation_deg'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('CSV wymaga kolumn time_utc,azimuth_deg,elevation_deg')
    return list(reader)

def normalize(rows):
    if not isinstance(rows,list) or not 1<=len(rows)<=5000:
        raise ValueError('Prześlij od 1 do 5000 pomiarów')
    clean=[];seen=set()
    for row in rows:
        t=utc(row['time_utc']).isoformat(timespec='microseconds').replace('+00:00','Z')
        a,e=float(row['azimuth_deg']),float(row['elevation_deg'])
        if not math.isfinite(a+e) or not 0<=a<360 or not -90<=e<=90:
            raise ValueError('Azymut: 0..360° bez 360; elewacja: -90..90°; liczby skończone')
        if t in seen:raise ValueError('Powtórzony czas w przesłanej partii')
        seen.add(t);clean.append({'time_utc':t,'azimuth_deg':a,'elevation_deg':e})
    return sorted(clean,key=lambda r:r['time_utc'])

class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,created TEXT,source TEXT,lat REAL,lon REAL,height REAL);
            CREATE TABLE IF NOT EXISTS measurements(session TEXT,time TEXT,az REAL,el REAL,
                PRIMARY KEY(session,time),FOREIGN KEY(session) REFERENCES sessions(id));
            ''')
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=15)
        try:
            c.execute('PRAGMA foreign_keys=ON')
            with c:yield c
        finally:c.close()
    def ingest(self,rows,station,source='manual',session_id=None):
        rows=normalize(rows);observer=Observer(**station)
        if source not in ('manual','csv','instrument','synthetic-demo','bluetooth-lx200-pointing'):raise ValueError('Nieznane źródło pomiarów')
        if session_id is not None:
            try:session_id=str(uuid.UUID(str(session_id)))
            except ValueError:raise ValueError('Niepoprawny identyfikator sesji')
        else:session_id=str(uuid.uuid4())
        with self.connect() as db:
            previous=db.execute('SELECT lat,lon,height,source FROM sessions WHERE id=?',(session_id,)).fetchone()
            values=(observer.latitude_deg,observer.longitude_deg,observer.elevation_m)
            if previous and (previous[:3]!=values or previous[3]!=source):raise ValueError('Stanowisko i źródło nie mogą zmieniać się w tej samej sesji')
            if not previous:
                db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(session_id,datetime.now(timezone.utc).isoformat(),source,*values))
            # Reject conflicting duplicates but make exact retransmissions idempotent.
            added=0
            for r in rows:
                old=db.execute('SELECT az,el FROM measurements WHERE session=? AND time=?',(session_id,r['time_utc'])).fetchone()
                pair=(r['azimuth_deg'],r['elevation_deg'])
                if old is not None:
                    if old!=pair:raise ValueError('Ten czas już istnieje z innym pomiarem; utwórz nową sesję')
                    continue
                db.execute('INSERT INTO measurements VALUES(?,?,?,?)',(session_id,r['time_utc'],*pair));added+=1
            count=db.execute('SELECT count(*) FROM measurements WHERE session=?',(session_id,)).fetchone()[0]
        return {'session_id':session_id,'added':added,'total':count}
    def read(self,session_id):
        with self.connect() as db:
            s=db.execute('SELECT lat,lon,height,source FROM sessions WHERE id=?',(session_id,)).fetchone()
            if s is None:raise ValueError('Nie znaleziono sesji')
            rows=db.execute('SELECT time,az,el FROM measurements WHERE session=? ORDER BY time',(session_id,)).fetchall()
        return {'session_id':session_id,'station':{'latitude_deg':s[0],'longitude_deg':s[1],'elevation_m':s[2]},
            'source':s[3],'observations':[{'time_utc':r[0],'azimuth_deg':r[1],'elevation_deg':r[2]} for r in rows]}
    def sessions(self):
        with self.connect() as db:
            rows=db.execute('SELECT s.id,s.created,s.source,count(m.time),min(m.time),max(m.time) FROM sessions s LEFT JOIN measurements m ON m.session=s.id GROUP BY s.id ORDER BY s.created DESC LIMIT 100').fetchall()
        return [dict(zip(['session_id','created','source','count','first_utc','last_utc'],r)) for r in rows]
