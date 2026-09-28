"""Frozen synthetic stress test; outputs all seeds, including any failures."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import timedelta
import csv
import json
import numpy as np
from timdr_orbit.catalog import load_catalog,utc
from timdr_orbit.orbit import Observer,predict,pass_events
from timdr_orbit.observations import unit,angles,separation,ResidualTracker,associate

ROOT=Path(__file__).resolve().parents[1]
cat=load_catalog(ROOT/'data/catalog_2026-09-28.json');site=Observer(52.2297,21.0122,110)
start=utc('2026-09-28T12:00:00Z')
events=pass_events(cat[0],start,start+timedelta(days=1),site)
peak=utc(next(r['time_utc'] for r in events if r['event']=='culmination'))
times=[peak+timedelta(seconds=2*i-120) for i in range(121)]
base_records=predict(cat[0],times,site)['records']
az=np.array([r['azimuth_deg'] for r in base_records]);el=np.array([r['elevation_deg'] for r in base_records])
base=unit(az,el);seconds=np.arange(len(times))*2
truth=unit(az+.2+.0002*seconds,el-.1+.0001*seconds)
results=[];example=[]
for seed in range(1000,1030):
    rng=np.random.default_rng(seed)
    measured=unit(az+.2+.0002*seconds+rng.normal(0,.03,len(times)),
                  el-.1+.0001*seconds+rng.normal(0,.03,len(times)))
    outliers=np.zeros(len(times),bool);outliers[25:100:27]=True
    measured[outliers]=unit(az[outliers]+5,el[outliers]+4)
    missing=np.zeros(len(times),bool);missing[12:100:11]=True;missing[-20:]=True
    f=ResidualTracker();pred=[];rejected=0
    for i,t in enumerate(times):
        state=f.step(t,base[i],None if missing[i] else measured[i]);pred.append(state['prior_unit'])
        if outliers[i] and not state['measurement_accepted']:rejected+=1
        if seed==1000 and not missing[i]:
            a,e=angles(measured[i]);example.append({'time_utc':t.isoformat(),'azimuth_deg':float(a),'elevation_deg':float(e)})
    err=separation(pred,truth);raw=separation(base,truth)
    rmse=lambda x:float(np.sqrt(np.mean(x*x)))
    results.append({'seed':seed,'raw_rmse_deg':rmse(raw[20:]),'filtered_prior_rmse_deg':rmse(err[20:]),
        'holdout_raw_rmse_deg':rmse(raw[-20:]),'holdout_filtered_rmse_deg':rmse(err[-20:]),
        'outliers_rejected':rejected,'outliers_total':int(outliers.sum())})
ratios=[r['filtered_prior_rmse_deg']/r['raw_rmse_deg'] for r in results]
held=[r['holdout_filtered_rmse_deg']/r['holdout_raw_rmse_deg'] for r in results]
match=associate(cat,example,site)
summary={'kind':'synthetic noisy angular measurements based on real catalog; no independent measured orbit truth',
    'seeds':30,'median_rmse_ratio':float(np.median(ratios)),'median_holdout_ratio':float(np.median(held)),
    'passed':bool(np.median(ratios)<.5 and np.median(held)<.5),'association':match,
    'runs':results}
out=ROOT/'artifacts/validation';out.mkdir(parents=True,exist_ok=True)
(out/'tracking_validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
with (out/'synthetic_observations.csv').open('w',newline='',encoding='utf-8') as stream:
    w=csv.DictWriter(stream,fieldnames=list(example[0]));w.writeheader();w.writerows(example)
print(json.dumps({k:v for k,v in summary.items() if k not in ['runs','association']},indent=2))
if not summary['passed']:sys.exit(1)
