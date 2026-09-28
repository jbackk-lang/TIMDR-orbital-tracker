"""SGP4 through Skyfield, explicit reference frames and geometric observables."""
from dataclasses import dataclass
from datetime import timedelta
import numpy as np
from skyfield.api import EarthSatellite, load, wgs84
from skyfield.framelib import itrs
from .catalog import utc, epoch_utc, validate

TS=load.timescale(builtin=True)  # Offline bundled timescale; no hidden network calls.

@dataclass(frozen=True)
class Observer:
    latitude_deg: float
    longitude_deg: float
    elevation_m: float=0.
    def __post_init__(self):
        if not all(np.isfinite(v) for v in (self.latitude_deg,self.longitude_deg,self.elevation_m)):
            raise ValueError('Observer coordinates must be finite')
        if not -90<=self.latitude_deg<=90 or not -180<=self.longitude_deg<=180:
            raise ValueError('Observer outside valid latitude/longitude bounds')
        if not -500<=self.elevation_m<=10000: raise ValueError('Unsupported observer elevation')
    def location(self):
        return wgs84.latlon(self.latitude_deg,self.longitude_deg,elevation_m=self.elevation_m)

def satellite(row):
    validate([row])
    fields={**row,'CENTER_NAME':'EARTH','REF_FRAME':'TEME','TIME_SYSTEM':'UTC','MEAN_ELEMENT_THEORY':'SGP4'}
    return EarthSatellite.from_omm(TS,fields)

def check_age(row,times,max_age_days=7.,allow_stale=False):
    if not np.isfinite(max_age_days) or max_age_days<=0: raise ValueError('Age limit must be positive')
    ages=[abs((utc(t)-epoch_utc(row['EPOCH'])).total_seconds())/86400 for t in times]
    age=max(ages)
    if age>max_age_days and not allow_stale:
        raise ValueError(f"{row['OBJECT_NAME']}: elements {age:.2f} days from requested time; limit {max_age_days}. Refresh catalog or explicitly allow stale predictions.")
    return age

def predict(row,times,observer,max_age_days=7.,allow_stale=False):
    times=[utc(t) for t in times]
    if not times: raise ValueError('Empty time sequence')
    age=check_age(row,times,max_age_days,allow_stale)
    sat=satellite(row); st=TS.from_datetimes(times)
    geo=sat.at(st)
    if any(m for m in np.atleast_1d(geo.message)):
        raise ValueError('SGP4 propagation error: '+str(geo.message))
    loc=observer.location()
    top=(sat-loc).at(st)
    alt,az,distance=top.altaz()  # No atmospheric refraction correction.
    sub=wgs84.subpoint(geo)
    fixed=geo.frame_xyz(itrs).km.T
    speed=np.linalg.norm(geo.velocity.km_per_s.T,axis=1)
    rv=np.sum(top.position.km.T*top.velocity.km_per_s.T,axis=1)/distance.km
    if not np.all(np.isfinite(fixed)): raise ValueError('Nonfinite propagated position')
    records=[]
    for i,t in enumerate(times):
        records.append({'time_utc':t.isoformat().replace('+00:00','Z'),
            'latitude_deg':float(sub.latitude.degrees[i]),'longitude_deg':float(sub.longitude.degrees[i]),
            'height_km':float(sub.elevation.km[i]),'azimuth_deg':float(az.degrees[i]),
            'elevation_deg':float(alt.degrees[i]),'range_km':float(distance.km[i]),
            'range_rate_km_s':float(rv[i]),'speed_gcrs_km_s':float(speed[i]),
            'position_itrs_km':fixed[i].tolist(),'position_gcrs_km':geo.position.km.T[i].tolist(),
            'above_geometric_horizon':bool(alt.degrees[i]>0)})
    return {'norad_id':int(row['NORAD_CAT_ID']),'name':row['OBJECT_NAME'],
        'epoch_utc':epoch_utc(row['EPOCH']).isoformat(),'max_element_age_days':age,
        'stale':age>max_age_days,'records':records}

def pass_events(row,start,end,observer,min_elevation=10.,max_age_days=7.,allow_stale=False):
    start,end=utc(start),utc(end)
    if end<=start or (end-start).total_seconds()>7*86400: raise ValueError('Pass window must be 0..7 days')
    if not 0<=min_elevation<90: raise ValueError('Minimum elevation must be 0..90 degrees')
    check_age(row,[start,end],max_age_days,allow_stale)
    sat=satellite(row)
    tt,events=sat.find_events(observer.location(),TS.from_datetime(start),TS.from_datetime(end),altitude_degrees=min_elevation)
    dates=list(tt.utc_datetime())
    if not dates:return []
    records=predict(row,dates,observer,max_age_days,allow_stale)['records']
    # Raw event sequence intentionally preserves partial passes at window edges.
    return [{**r,'event':('rise','culmination','set')[int(e)]} for r,e in zip(records,events)]

def grid(start,hours=3.,step_seconds=30.):
    start=utc(start)
    if not np.isfinite(hours) or not np.isfinite(step_seconds) or not 0<hours<=168 or step_seconds<=0:
        raise ValueError('Require 0<hours<=168 and positive step')
    n=int(hours*3600/step_seconds)+1
    if n<2 or n>25000:raise ValueError('Time grid must contain 2..25000 samples')
    return [start+timedelta(seconds=float(i*step_seconds)) for i in range(n)]
