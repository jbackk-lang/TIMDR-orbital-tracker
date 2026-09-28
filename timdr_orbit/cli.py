import argparse
import csv
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
from .catalog import fetch_catalog,load_catalog,utc
from .orbit import Observer,grid,predict,pass_events
from .observations import associate,track_observations
from .report import write_report

def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def main():
    p=argparse.ArgumentParser(description='TIMDR: public-catalog orbit tracking and observation association')
    sub=p.add_subparsers(dest='command',required=True)
    server=sub.add_parser('serve');server.add_argument('--catalog',required=True);server.add_argument('--port',type=int,default=8766)
    server.add_argument('--runtime',default='runtime');server.add_argument('--example',default=None)
    f=sub.add_parser('fetch');f.add_argument('--ids',nargs='+',type=int,required=True);f.add_argument('--out',required=True)
    for cmd in ('predict','associate','track'):
        a=sub.add_parser(cmd);a.add_argument('--catalog',required=True)
        a.add_argument('--lat',type=float,required=True);a.add_argument('--lon',type=float,required=True)
        a.add_argument('--height',type=float,default=0.);a.add_argument('--out',required=True)
        if cmd=='predict':
            a.add_argument('--start',default=None,help='ISO UTC; default current UTC')
            a.add_argument('--hours',type=float,default=3.);a.add_argument('--step',type=float,default=30.)
            a.add_argument('--pass-hours',type=float,default=24.);a.add_argument('--min-elevation',type=float,default=10.)
            a.add_argument('--allow-stale',action='store_true')
        else:
            a.add_argument('--observations',required=True,help='CSV: time_utc,azimuth_deg,elevation_deg')
            if cmd=='track':a.add_argument('--id',type=int,required=True);a.add_argument('--sigma-deg',type=float,default=.03)
    spin=sub.add_parser('spin');spin.add_argument('--csv',required=True);spin.add_argument('--f-bounds',nargs=2,type=float,required=True)
    spin.add_argument('--drift-bounds',nargs=2,type=float,required=True);spin.add_argument('--out',required=True)
    args=p.parse_args()
    try:
        if args.command=='serve':
            from .server import serve
            serve(args.catalog,args.runtime,args.port,args.example);return
        if args.command=='fetch':
            rows=fetch_catalog(args.ids,args.out);print(f'Saved {len(rows)} objects: {Path(args.out).resolve()}');return
        if args.command=='spin':
            import numpy as np
            from .rotation_clock import fit_clock
            d=np.genfromtxt(args.csv,delimiter=',',names=True)
            result,clock=fit_clock(d['time'],d['flux'],args.f_bounds,args.drift_bounds)
            dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
            save(dest.with_suffix('.json'),result)
            np.savetxt(dest.with_suffix('.csv'),clock,delimiter=',',header='time,frequency,relative_photometric_angle_radians',comments='')
        else:
            catalog=load_catalog(args.catalog);observer=Observer(args.lat,args.lon,args.height)
            if args.command=='predict':
                start=utc(args.start) if args.start else datetime.now(timezone.utc)
                times=grid(start,args.hours,args.step)
                objects=[]
                for row in catalog:
                    obj=predict(row,times,observer,allow_stale=args.allow_stale)
                    obj['pass_events']=pass_events(row,start,start+timedelta(hours=args.pass_hours),observer,args.min_elevation,allow_stale=args.allow_stale)
                    objects.append(obj)
                result={'model':'SGP4 / Skyfield','version':'0.1.0',
                    'generated_at_utc':datetime.now(timezone.utc).isoformat(),'observer':asdict(observer),
                    'catalog_sha256':hashlib.sha256(Path(args.catalog).read_bytes()).hexdigest(),
                    'minimum_pass_elevation_deg':args.min_elevation,'pass_window_hours':args.pass_hours,
                    'scope':'Catalog predictions; above horizon is not optical visibility; no collision probability or measured position uncertainty',
                    'objects':objects}
                dest=Path(args.out);dest.mkdir(parents=True,exist_ok=True)
                save(dest/'prediction.json',result);write_report(result,dest/'dashboard.html')
                with (dest/'tracks.csv').open('w',encoding='utf-8',newline='') as stream:
                    fields=['norad_id','name','time_utc','latitude_deg','longitude_deg','height_km','azimuth_deg','elevation_deg','range_km','range_rate_km_s','speed_gcrs_km_s','above_geometric_horizon']
                    writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader()
                    for obj in objects:
                        for r in obj['records']:writer.writerow({'norad_id':obj['norad_id'],'name':obj['name'],**r})
            else:
                with open(args.observations,encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
                if args.command=='associate':result=associate(catalog,rows,observer)
                else:
                    matches=[r for r in catalog if int(r['NORAD_CAT_ID'])==args.id]
                    if not matches:raise ValueError('Requested object not in catalog')
                    result=track_observations(matches[0],rows,observer,args.sigma_deg)
                save(args.out,result)
        print('Saved: '+str(Path(args.out).resolve()))
    except (ValueError,KeyError,OSError) as exc:
        p.exit(2,'Error: '+str(exc)+'\n')

if __name__=='__main__':main()
