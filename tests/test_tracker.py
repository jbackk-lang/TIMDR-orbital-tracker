import copy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from sgp4.api import Satrec
from timdr_orbit.catalog import load_catalog,utc,validate
from timdr_orbit.orbit import Observer,grid,predict,pass_events,satellite,TS
from timdr_orbit.observations import unit,angles,separation,associate,ResidualTracker,validate_observations
from timdr_orbit.report import write_report

ROOT=Path(__file__).resolve().parents[1]
CAT=load_catalog(ROOT/'data/catalog_2026-09-28.json')
SITE=Observer(52.2297,21.0122,110)
START=utc('2026-09-28T12:00:00Z')

class TrackerTests(unittest.TestCase):
    def test_published_vallado_reference(self):
        # Reference: Vallado et al., Revisiting Spacetrack Report #3 (2006),
        # SGP4-VER.TLE / tcppver.out distributed with python-sgp4.
        sat=Satrec.twoline2rv('1 00005U 58002B   00179.78495062  .00000023  00000-0  28098-4 0  4753',
                            '2 00005  34.2682 348.7242 1859667 331.7664  19.3264 10.82419157413667')
        expected=[[7022.46529266,-1400.08296755,.03995155],[-7154.03120202,-3783.17682504,-3536.19412294],[-7134.59340119,6531.68641334,3260.27186483]]
        for minute,ref in zip([0,360,720],expected):
            err,r,v=sat.sgp4_tsince(minute)
            self.assertEqual(err,0);np.testing.assert_allclose(r,ref,atol=1e-5,rtol=0)
    def test_utc_requires_zone(self):
        with self.assertRaises(ValueError):utc('2026-09-28T12:00:00')
        self.assertEqual(utc('2026-09-28T14:00:00+02:00'),START)
    def test_stale_rejected(self):
        with self.assertRaises(ValueError):predict(CAT[0],[START+timedelta(days=30)],SITE)
        self.assertTrue(predict(CAT[0],[START+timedelta(days=30)],SITE,allow_stale=True)['stale'])
    def test_catalog_constraints(self):
        with self.assertRaises(ValueError):validate([CAT[0],CAT[0]])
        r=copy.deepcopy(CAT[0]);r['REF_FRAME']='GCRF'
        with self.assertRaises(ValueError):validate([r])
    def test_observer_and_grid_constraints(self):
        with self.assertRaises(ValueError):Observer(91,0)
        with self.assertRaises(ValueError):grid(START,step_seconds=0)
        with self.assertRaises(ValueError):grid(START,hours=200)
    def test_predictions_and_geodetic_roundtrip(self):
        p=predict(CAT[0],[START],SITE)['records'][0]
        self.assertTrue(300<p['height_km']<600)
        self.assertTrue(7<p['speed_gcrs_km_s']<8.5)
        self.assertTrue(0<=p['azimuth_deg']<360)
        from skyfield.api import wgs84
        point=wgs84.latlon(p['latitude_deg'],p['longitude_deg'],elevation_m=p['height_km']*1000)
        np.testing.assert_allclose(point.itrs_xyz.km,p['position_itrs_km'],atol=1e-5)
    def test_range_rate_finite_difference(self):
        times=[START+timedelta(seconds=s) for s in [-.2,0,.2]]
        r=predict(CAT[0],times,SITE)['records']
        self.assertAlmostEqual((r[2]['range_km']-r[0]['range_km'])/.4,r[1]['range_rate_km_s'],places=4)
    def test_pass_threshold(self):
        ev=pass_events(CAT[0],START,START+timedelta(days=1),SITE)
        self.assertTrue(ev)
        for r in ev:
            if r['event'] in ['rise','set']:self.assertLess(abs(r['elevation_deg']-10),.05)
    def test_unit_wrap_and_zenith(self):
        self.assertAlmostEqual(float(separation(unit(359.9,0),unit(.1,0))),.2)
        self.assertLess(float(separation(unit(0,90),unit(270,90))),1e-10)
    def rows(self):
        records=predict(CAT[0],grid(START,hours=.05,step_seconds=5),SITE)['records']
        return [{'time_utc':r['time_utc'],'azimuth_deg':(r['azimuth_deg']+.02)%360,'elevation_deg':r['elevation_deg']+.01} for r in records]
    def test_association(self):self.assertEqual(associate(CAT,self.rows(),SITE)['norad_id'],25544)
    def test_ambiguity(self):
        twin=copy.deepcopy(CAT[0]);twin['NORAD_CAT_ID']=99999
        self.assertEqual(associate([CAT[0],twin],self.rows(),SITE)['status'],'ambiguous')
    def test_unknown_rejected(self):
        rows=self.rows()
        for r in rows:r['azimuth_deg']=(r['azimuth_deg']+90)%360
        self.assertEqual(associate(CAT,rows,SITE)['status'],'unmatched')
    def test_outlier_and_covariance(self):
        f=ResidualTracker();b=unit(40,20)
        for i in range(20):f.step(START+timedelta(seconds=i),b,unit(40.1,20.05))
        bad=f.step(START+timedelta(seconds=20),b,unit(100,60))
        self.assertFalse(bad['measurement_accepted'])
        self.assertGreaterEqual(np.linalg.eigvalsh(f.P).min(),-1e-15)
    def test_predictions_precede_measurement(self):
        a=ResidualTracker();b=ResidualTracker();base=unit(30,40)
        x=a.step(START,base,unit(30.2,40));y=b.step(START,base,unit(29.9,40))
        np.testing.assert_array_equal(x['prior_unit'],y['prior_unit'])
    def test_bad_observation_time(self):
        rows=self.rows();rows[1]['time_utc']=rows[0]['time_utc']
        with self.assertRaises(ValueError):validate_observations(rows)
    def test_report_escapes_untrusted_names(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'report.html';write_report({'name':'</script><script>evil()</script>'},path)
            self.assertNotIn('</script><script>evil()',path.read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
