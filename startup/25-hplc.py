import uuid
import time
from enum import Enum
from ophyd import (EpicsSignal, EpicsSignalRO, Device, Component as Cpt)

class HPLCStatus(str, Enum):
    idle = "idle"
    waiting_injected = "waiting_injected"
    waiting_done = "waiting_done"

class HPLC(Device):
    ready = Cpt(EpicsSignal, 'io1')
    injected = Cpt(EpicsSignalRO, 'io2')
    done = Cpt(EpicsSignalRO, 'io3')
    bypass = Cpt(EpicsSignal, '_bypass')
    
    def __init__(self, *args, reg, read_filepath, write_filepath, **kwargs):
        self.hplc_status = HPLCStatus.idle
        self._injected_status = None
        self._done_status = None
        self._bypass_status = None
        self._resource = None
        self.reg = reg
        self._read_filepath = read_filepath
        self._write_filepath = write_filepath
        super().__init__(*args, **kwargs)

    def stage(self):
        # self._resource = self.reg.insert_resource("HPLC1", self._read_filepath)
        self.injected.subscribe(self._injected_changed)
        self.done.subscribe(self._done_changed)
        self.bypass.subscribe(self._bypass_changed)

    def unstage(self):
        self.injected.clear_sub(self._injected_changed)
        self.done.clear_sub(self._done_changed)
        self.bypass.clear_sub(self._bypass_changed)
        self._injected_status = None
        self._done_status = None
        self._bypass_status = None
        # self._resource = None

    def kickoff(self):
        """
        Set 'ready' to True and return a status object tied to 'injected'.
        """
        self.ready.set(1)
        self.hplc_status = HPLCStatus.waiting_injected
        self._injected_status = DeviceStatus(self.injected)
        self._done_status = DeviceStatus(self.done)
        return self._injected_status

    def complete(self):
        """
        Return a status object tied to 'done'.
        """
        if self._done_status is None:
            raise RuntimeError("must call kickoff() before complete()")
        return self._done_status

    def collect(self):
        """
        Yield events that reference the data files generated by HPLC.
        """
        import numpy as np
        # TODO Decide whether you want to 'chunk' the dataset into 'events'.
        # Insert a datum per event and yield a partial event document.
        for i in range(1):
            yield {'time': time.time(),
                   'seq_num': i+1,
                   'data': {'foo': np.random.rand(2048, 1)},  #datum_id},
                   'timestamps': {'foo': time.time()}}

    def describe_collect(self):
        return {self.name: {'foo': {'dtype': 'array',
                             'shape': (2048,),
                             'source': 'TO DO'}}}

    def _injected_changed(self, value, old_value, **kwargs):
        """Mark the status object returned by 'kickoff' as finished when
        injected goes from 0 to 1."""
        if self._injected_status is None:
            return
        if (old_value == 0) and (value == 1):
            self.ready.set(0)
            self.hplc_status = HPLCStatus.waiting_done
            self._injected_status._finished()

    def _done_changed(self, value, old_value, **kwargs):
        """Mark the status object returned by 'complete' as finished when
        done goes from 0 to 1."""
        if self._done_status is None:
            return
        if (old_value == 0) and (value == 1):
            self.hplc_status = HPLCStatus.idle
            self._done_status._finished()

    def _bypass_changed(self, value, old_value, **kwargs):
        """Mark the status object returned by 'complete' as finished when
        done goes from 0 to 1."""
        if value == 0:
            return
        print('Bypass used: {}, hplc state: {}'.format(value, self.hplc_status))
        if (value == 1) and self.hplc_status == HPLCStatus.waiting_injected:
            self._injected_changed(1,0)
        elif (value == 2) and self.hplc_status == HPLCStatus.waiting_done:
            self._done_changed(1,0)
        self.bypass.set(0)

hplc = HPLC('XF:16IDC-ES:Sol{ctrl}HPLC', name='hplc', reg=None, read_filepath=None, write_filepath=None)

def read_Shimadzu_section(section):
    """ the chromtographic data section starts with a header
        followed by 2-column data
        the input is a collection of strings
    """
    xdata = []
    ydata = []
    for line in section:
        tt = line.split()
        if len(tt)==2:
            try:
                x=float(tt[0])
            except ValueError:
                continue
            try:
                y=float(tt[1])
            except ValueError:
                continue
            xdata.append(x)
            ydata.append(y)
    return xdata,ydata

def read_Shimadzu_datafile(fn):
    """ read the ascii data from Shimadzu Lab Solutions software
        the file appear to be split in to multiple sections, each starts with [section name], 
        and ends with a empty line
        returns the data in the sections titled 
            [LC Chromatogram(Detector A-Ch1)] and [LC Chromatogram(Detector B-Ch1)]
    """
    fd = open(fn, "r")
    lines = fd.read().split('\n')
    fd.close()
    
    sections = []
    while True:
        try:
            idx = lines.index('')
        except ValueError:
            break
        if idx>0:
            sections.append(lines[:idx])
        lines = lines[idx+1:]
    
    data = []
    for s in sections:
        if s[0][:16]=="[LC Chromatogram":
            x,y = read_Shimadzu_section(s)
            data.append([s[0],x,y])
    
    return data

