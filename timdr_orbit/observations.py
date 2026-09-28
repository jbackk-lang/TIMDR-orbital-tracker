"""Catalog association and causal line-of-sight residual tracking.

This corrects pointing over a short arc. It does not determine a new 6D orbit.
"""
import numpy as np
from .catalog import utc
from .orbit import predict

def unit(az_deg,el_deg):
    a,e=np.radians(az_deg),np.radians(el_deg)
    return np.stack([np.cos(e)*np.sin(a),np.cos(e)*np.cos(a),np.sin(e)],axis=-1)

def angles(v):
    v=np.asarray(v); v=v/np.linalg.norm(v,axis=-1,keepdims=True)
    return np.degrees(np.arctan2(v[...,0],v[...,1]))%360,np.degrees(np.arcsin(np.clip(v[...,2],-1,1)))

def separation(u,v):
    u=np.asarray(u);v=np.asarray(v)
    return np.degrees(np.arctan2(np.linalg.norm(np.cross(u,v),axis=-1),np.sum(u*v,axis=-1)))

def validate_observations(rows):
    if len(rows)<5: raise ValueError('At least five observations are required')
    times=[utc(r['time_utc']) for r in rows]
    if any(b<=a for a,b in zip(times,times[1:])): raise ValueError('Observations must have strictly increasing timestamps')
    for r in rows:
        a,e=float(r['azimuth_deg']),float(r['elevation_deg'])
        if not np.isfinite(a+e) or not 0<=a<360 or not -90<=e<=90: raise ValueError('Invalid observed angles')
    return times,unit([float(r['azimuth_deg']) for r in rows],[float(r['elevation_deg']) for r in rows])

def associate(catalog,rows,observer,gate_deg=1.,margin_deg=.2):
    if gate_deg<=0 or margin_deg<0:raise ValueError('Invalid association gates')
    times,observed=validate_observations(rows)
    scores=[];excluded=[]
    for row in catalog:
        try:r=predict(row,times,observer)['records']
        except ValueError as exc:
            excluded.append({'norad_id':int(row['NORAD_CAT_ID']),'reason':str(exc)});continue
        expected=unit([x['azimuth_deg'] for x in r],[x['elevation_deg'] for x in r])
        errors=separation(observed,expected)
        scores.append({'norad_id':int(row['NORAD_CAT_ID']),'name':row['OBJECT_NAME'],
            'median_error_deg':float(np.median(errors)),'inlier_fraction':float(np.mean(errors<=gate_deg))})
    scores.sort(key=lambda x:x['median_error_deg'])
    match=None;status='unmatched'
    if scores and scores[0]['median_error_deg']<=gate_deg and scores[0]['inlier_fraction']>=.7:
        if len(scores)>1 and scores[1]['median_error_deg']-scores[0]['median_error_deg']<margin_deg:
            status='ambiguous'
        else:status='matched';match=scores[0]['norad_id']
    return {'status':status,'norad_id':match,'candidates':scores,'excluded':excluded,
            'scope':'Association within the supplied catalog only; not proof of global uniqueness'}

class ResidualTracker:
    """Constant-velocity ENU unit-vector residual, Kalman filter with gating.

    Measurements and predictions stay separate: step() returns the PRIOR pointing
    before assimilating the current sample. Joseph covariance update preserves PSD.
    """
    def __init__(self,sigma_deg=.03,accel_sigma_deg=.0003,initial_bias_deg=.5,max_gap_s=120):
        if min(sigma_deg,accel_sigma_deg,initial_bias_deg,max_gap_s)<=0:raise ValueError('Tracker scales must be positive')
        self.sigma=np.radians(sigma_deg);self.q=np.radians(accel_sigma_deg)**2
        self.initial=np.radians(initial_bias_deg);self.max_gap=max_gap_s
        self.x=np.zeros(6);self.P=np.diag([self.initial**2]*3+[np.radians(.01)**2]*3)
        self.last=None
    def step(self,time,expected,measurement=None):
        time=utc(time);dt=0. if self.last is None else (time-self.last).total_seconds()
        if dt<0 or (self.last is not None and dt==0):raise ValueError('Tracker time must increase')
        if dt>self.max_gap:
            self.x[:]=0;self.P=np.diag([self.initial**2]*3+[np.radians(.01)**2]*3);dt=0.
        F=np.eye(6);F[:3,3:]=np.eye(3)*dt
        Q=self.q*np.block([[np.eye(3)*dt**4/4,np.eye(3)*dt**3/2],
                          [np.eye(3)*dt**3/2,np.eye(3)*dt**2]])
        self.x=F@self.x;self.P=F@self.P@F.T+Q
        expected=np.asarray(expected,float)
        prior=expected+self.x[:3];prior/=np.linalg.norm(prior)
        accepted=False;nis=None
        if measurement is not None:
            H=np.column_stack([np.eye(3),np.zeros((3,3))]);R=np.eye(3)*self.sigma**2
            innovation=np.asarray(measurement)-expected-H@self.x
            S=H@self.P@H.T+R
            nis=float(innovation@np.linalg.solve(S,innovation))
            if nis<=16.27:  # Approximate 99.9% chi-square gate, 3 components.
                K=np.linalg.solve(S,(self.P@H.T).T).T
                self.x+=K@innovation
                A=np.eye(6)-K@H
                self.P=A@self.P@A.T+K@R@K.T
                accepted=True
        self.last=time
        return {'prior_unit':prior,'measurement_accepted':accepted,'innovation_statistic':nis,
                'formal_pointing_sigma_deg':float(np.degrees(np.sqrt(np.trace(self.P[:3,:3]))))}

def track_observations(row,rows,observer,sigma_deg=.03):
    times,measured=validate_observations(rows)
    predicted=predict(row,times,observer)['records']
    base=unit([r['azimuth_deg'] for r in predicted],[r['elevation_deg'] for r in predicted])
    filt=ResidualTracker(sigma_deg=sigma_deg);out=[]
    for t,b,m,r in zip(times,base,measured,rows):
        state=filt.step(t,b,m);a,e=angles(state.pop('prior_unit'))
        out.append({'time_utc':r['time_utc'],'predicted_azimuth_deg':float(a),
            'predicted_elevation_deg':float(e),**state})
    return {'norad_id':int(row['NORAD_CAT_ID']),'records':out,
        'scope':'Causal one-step pointing predictions, not orbit determination; sigma is uncalibrated formal filter covariance'}
