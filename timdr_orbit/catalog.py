"""CelesTrak OMM-compatible JSON, with explicit provenance and no silent fallback."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import math

def utc(value):
    if isinstance(value, datetime):
        d=value
    else:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if d.tzinfo is None:
        raise ValueError('Timestamp must contain UTC Z or an explicit timezone offset')
    return d.astimezone(timezone.utc)

def epoch_utc(value):
    # CelesTrak GP specifies UTC even when its ISO timestamp lacks the suffix.
    d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def validate(rows):
    if not isinstance(rows,list) or not rows:
        raise ValueError('Expected a nonempty list of OMM-compatible records')
    seen=set()
    fields=('MEAN_MOTION','ECCENTRICITY','INCLINATION','RA_OF_ASC_NODE',
            'ARG_OF_PERICENTER','MEAN_ANOMALY','BSTAR','MEAN_MOTION_DOT','MEAN_MOTION_DDOT')
    for row in rows:
        n=int(row['NORAD_CAT_ID'])
        if n<=0 or n in seen: raise ValueError('Catalog IDs must be unique positive integers')
        seen.add(n)
        epoch_utc(row['EPOCH'])
        if not all(math.isfinite(float(row[f])) for f in fields): raise ValueError('Nonfinite orbital elements')
        if not 0<=float(row['ECCENTRICITY'])<1 or float(row['MEAN_MOTION'])<=0:
            raise ValueError('Only bound Earth orbits with positive mean motion are supported')
        if not 0<=float(row['INCLINATION'])<=180: raise ValueError('Invalid inclination')
        for field,expected in [('CENTER_NAME','EARTH'),('REF_FRAME','TEME'),('TIME_SYSTEM','UTC'),('MEAN_ELEMENT_THEORY','SGP4')]:
            if str(row.get(field,expected)).upper()!=expected: raise ValueError('Unsupported '+field)
    return rows

def load_catalog(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8-sig')))

def fetch_catalog(ids, destination):
    """Explicit fetch; existing snapshots are never overwritten."""
    path=Path(destination)
    if path.exists() or path.with_suffix('.meta.json').exists():
        raise FileExistsError('Use a new snapshot filename; historical snapshots are immutable')
    rows=[]; sources=[]
    for ident in dict.fromkeys(ids):
        if int(ident)<=0: raise ValueError('Invalid catalog ID')
        url='https://celestrak.org/NORAD/elements/gp.php?'+urlencode({'CATNR':int(ident),'FORMAT':'JSON'})
        request=Request(url,headers={'User-Agent':'TIMDR-orbital-tracker/0.1 research'})
        with urlopen(request,timeout=45) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('Catalog response exceeds size limit')
        received=validate(json.loads(raw))
        if len(received)!=1 or int(received[0]['NORAD_CAT_ID'])!=int(ident):
            raise ValueError('Source returned an unexpected catalog object')
        rows.extend(received); sources.append(url)
    validate(rows)
    path.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(rows,indent=2,ensure_ascii=False).encode('utf-8')
    with path.open('xb') as f: f.write(content)
    meta={'downloaded_at_utc':datetime.now(timezone.utc).isoformat(),'sources':sources,
          'sha256':hashlib.sha256(content).hexdigest(),'provider':'CelesTrak GP',
          'kind':'catalog mean elements, not independent position measurements'}
    path.with_suffix('.meta.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return rows
