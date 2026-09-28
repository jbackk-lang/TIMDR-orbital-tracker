import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from timdr_orbit.storage import Store,normalize,parse_csv
from timdr_orbit.bluetooth import LX200Reader,parse_angle
from timdr_orbit.server import Application,make_server

ROOT=Path(__file__).resolve().parents[1]
STATION={'latitude_deg':52.2297,'longitude_deg':21.0122,'elevation_m':110}
SAMPLE={'time_utc':'2026-09-28T12:00:00Z','azimuth_deg':120.,'elevation_deg':30.}

class FakeSerial:
    def __init__(self,replies):self.replies=iter(replies);self.commands=[]
    def write(self,command):self.commands.append(command)
    def read_until(self,*args,**kwargs):return next(self.replies)

class InputTests(unittest.TestCase):
    def test_lx200_readonly_queries(self):
        serial=FakeSerial([b'123*30:00#',b'+45*15:30#']);reader=LX200Reader(serial)
        sample=reader.sample()
        self.assertEqual(serial.commands,[b':GZ#',b':GA#'])
        self.assertAlmostEqual(sample['azimuth_deg'],123.5)
        self.assertAlmostEqual(sample['elevation_deg'],45.258333333)
        with self.assertRaises(ValueError):reader.query(b':MS#','azimuth')
    def test_lx200_formats_and_sign(self):
        self.assertEqual(parse_angle(b'-00*30#','elevation'),-.5)
        self.assertEqual(parse_angle(b'360\xdf00#','azimuth'),0)
        self.assertAlmostEqual(parse_angle("+10*20'30#",'elevation'),10+20/60+30/3600)
    def test_lx200_corrupt_timeout(self):
        for value in [b'123*70#',b'nan#',b'999*00#']:
            with self.assertRaises(ValueError):parse_angle(value,'azimuth')
        with self.assertRaises(TimeoutError):LX200Reader(FakeSerial([b'123*30'])).sample()
    def test_csv_validation(self):
        rows=parse_csv('time_utc,azimuth_deg,elevation_deg\n2026-09-28T12:00:00Z,120,30\n')
        self.assertEqual(normalize(rows)[0]['azimuth_deg'],120)
        with self.assertRaises(ValueError):parse_csv('time,az,el\n1,2,3')
        with self.assertRaises(ValueError):normalize([{**SAMPLE,'azimuth_deg':'nan'}])
    def test_time_order_including_subseconds(self):
        rows=normalize([{**SAMPLE,'time_utc':'2026-09-28T12:00:00.1Z'},SAMPLE])
        self.assertTrue(rows[0]['time_utc'].endswith('00.000000Z'))
    def test_durable_idempotent_store_and_atomic_conflicts(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'data.sqlite');r=s.ingest([SAMPLE],STATION)
            self.assertEqual(s.ingest([SAMPLE],STATION,session_id=r['session_id'])['added'],0)
            new={**SAMPLE,'time_utc':'2026-09-28T12:00:01Z'}
            with self.assertRaises(ValueError):s.ingest([new,{**SAMPLE,'azimuth_deg':50}],STATION,session_id=r['session_id'])
            reopened=Store(Path(d)/'data.sqlite')
            self.assertEqual(len(reopened.read(r['session_id'])['observations']),1)
            with self.assertRaises(ValueError):s.ingest([new],{**STATION,'elevation_m':120},session_id=r['session_id'])
    def test_http_receive_csv_and_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            app=Application(ROOT/'data/catalog_2026-09-28.json',d)
            server=make_server(app,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            def post(path,body,key=None):
                req=Request(base+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-TIMDR-Key':key or app.token})
                with urlopen(req,timeout=5) as response:return json.load(response)
            try:
                text=(ROOT/'artifacts/validation/synthetic_observations.csv').read_text()
                result=post('/api/import-csv',{'csv':text,'station':STATION,'source':'synthetic-demo'})
                self.assertGreaterEqual(result['total'],5)
                analysis=post('/api/analyze',{'session_id':result['session_id']})
                self.assertEqual(analysis['association']['norad_id'],25544)
                self.assertTrue(analysis['tracking']['records'])
                with self.assertRaises(HTTPError) as caught:post('/api/measurements',{},key='invalid')
                self.assertEqual(caught.exception.code,403)
                with self.assertRaises(HTTPError):post('/api/measurements',{'observations':[{**SAMPLE,'elevation_deg':100}],'station':STATION})
                with self.assertRaises(HTTPError):urlopen(Request(base+'/api/config',headers={'Origin':'https://example.com'}),timeout=5)
            finally:server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':unittest.main()
