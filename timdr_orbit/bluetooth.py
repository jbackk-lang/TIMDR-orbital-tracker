"""Read-only LX200 pointing through a paired Bluetooth SPP / serial COM port.

Only :GZ# and :GA# are transmitted. No slew, sync, park, tracking-rate or setting
commands exist in this adapter. BLE GATT and other telescope protocols unsupported.
"""
from datetime import datetime,timezone
import math
import re
import threading
import time
from .orbit import Observer

def ports():
    from serial.tools import list_ports
    return [{'device':p.device,'description':p.description} for p in list_ports.comports()]

def parse_angle(raw,kind):
    if isinstance(raw,bytes):raw=raw.decode('latin1')
    match=re.fullmatch(r'([+-]?)(\d{2,3})[\*\xdf\xb0](\d{2})(?:[:\x27\u2019](\d{2}(?:\.\d+)?))?#',raw.strip())
    if not match:raise ValueError('Niepoprawna odpowiedź LX200: oczekiwano kąta zakończonego #')
    sign,degrees,minutes,seconds=match.groups();minutes=int(minutes);seconds=float(seconds or 0)
    if minutes>=60 or seconds>=60:raise ValueError('Niepoprawne minuty/sekundy LX200')
    value=(int(degrees)+minutes/60+seconds/3600)*(-1 if sign=='-' else 1)
    if kind=='azimuth':
        if not 0<=value<=360:raise ValueError('Azymut LX200 poza zakresem')
        return value%360
    if kind!='elevation' or not -90<=value<=90:raise ValueError('Elewacja LX200 poza zakresem')
    return value

class LX200Reader:
    def __init__(self,transport):self.transport=transport
    def query(self,command,kind):
        if command not in (b':GZ#',b':GA#'):raise ValueError('Only read-only pointing queries permitted')
        self.transport.write(command)
        response=self.transport.read_until(b'#',size=32)
        if not response.endswith(b'#'):raise TimeoutError('Brak pełnej odpowiedzi LX200; sprawdź protokół, port i szybkość')
        return parse_angle(response,kind)
    def sample(self):
        start=datetime.now(timezone.utc);tick=time.monotonic()
        az=self.query(b':GZ#','azimuth');el=self.query(b':GA#','elevation')
        end=datetime.now(timezone.utc);span=time.monotonic()-tick
        if span>2.:raise TimeoutError('Odczyt dwóch osi trwał ponad 2 s; odrzucono niespójny czasowo pomiar')
        return {'time_utc':(start+(end-start)/2).isoformat(),'azimuth_deg':az,'elevation_deg':el,
            'acquisition_span_s':span}

class BluetoothCapture:
    def __init__(self,store):
        self.store=store;self.thread=None;self.stop_event=threading.Event();self.lock=threading.Lock()
        self.state={'running':False,'count':0,'error':None,'session_id':None}
    def status(self):
        with self.lock:return dict(self.state)
    def start(self,port,station,baudrate=9600,interval_s=1.):
        Observer(**station)
        if not math.isfinite(interval_s) or not .5<=interval_s<=60:raise ValueError('Odstęp musi wynosić 0,5..60 sekund')
        if baudrate not in (9600,19200,38400,57600,115200):raise ValueError('Nieobsługiwana szybkość portu')
        if port not in [p['device'] for p in ports()]:raise ValueError('Wybierz wykryty port COM; najpierw sparuj urządzenie w Windows')
        with self.lock:
            if self.thread is not None and self.thread.is_alive():raise ValueError('Odczyt już trwa')
            self.state={'running':True,'count':0,'error':None,'session_id':None,'port':port,
                'measurement_kind':'telescope_pointing_not_confirmed_object_detection'}
            self.stop_event.clear()
            self.thread=threading.Thread(target=self._run,args=(port,station,baudrate,interval_s),daemon=True)
            self.thread.start()
        return self.status()
    def _run(self,port,station,baudrate,interval_s):
        import serial
        try:
            # Avoid deliberately asserting modem control pins on connection.
            device=serial.Serial(port=None,baudrate=baudrate,timeout=.8,write_timeout=.8,
                bytesize=8,parity='N',stopbits=1,xonxoff=False,rtscts=False,dsrdtr=False)
            device.dtr=False;device.rts=False;device.port=port;device.open()
            with device:
                reader=LX200Reader(device);session_id=None
                while not self.stop_event.is_set():
                    sample=reader.sample()
                    result=self.store.ingest([sample],station,'bluetooth-lx200-pointing',session_id)
                    session_id=result['session_id']
                    with self.lock:self.state.update(count=result['total'],session_id=session_id,last_sample=sample)
                    self.stop_event.wait(interval_s)
        except (OSError,ValueError) as exc:
            with self.lock:self.state['error']=str(exc)
        finally:
            with self.lock:self.state['running']=False
    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=3)
        return self.status()
