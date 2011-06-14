from cStringIO import StringIO
import os
import sys
import tempfile
from unittest import TestCase

from pyrrd.exceptions import ExternalCommandError
from pyrrd.rrd import DataSource, RRA, RRD


class ExternalBackendTestCase(TestCase):

    def setUp(self):
        ds = [
            DataSource(dsName="speed", dsType="COUNTER", heartbeat=600)]
        rra = [
            RRA(cf="AVERAGE", xff=0.5, steps=1, rows=24),
            RRA(cf="AVERAGE", xff=0.5, steps=6, rows=10)]
        self.rrdfile = tempfile.NamedTemporaryFile()
        self.rrd = RRD(self.rrdfile.name, ds=ds, rra=rra, start=920804400)
        self.rrd.create()

    def test_updateError(self):
        self.rrd.bufferValue(1261214678, 612)
        self.rrd.bufferValue(1261214678, 612)
        self.assertRaises(ExternalCommandError, self.rrd.update)
        try:
            self.rrd.update()
        except ExternalCommandError, error:
            self.assertEquals(str(error), 
            ("ERROR: illegal attempt to update using time 1261214678 "
             "when last update time is 1261214678 (minimum one second step)"))

    def test_infoWriteMode(self):
        expectedOutput = """
            rra = [{'rows': 24, 'database': None, 'cf': 'AVERAGE', 'cdp_prep': None, 'beta': None, 'seasonal_period': None, 'steps': 1, 'window_length': None, 'threshold': None, 'alpha': None, 'pdp_per_row': None, 'xff': 0.5, 'ds': [], 'gamma': None, 'rra_num': None}, {'rows': 10, 'database': None, 'cf': 'AVERAGE', 'cdp_prep': None, 'beta': None, 'seasonal_period': None, 'steps': 6, 'window_length': None, 'threshold': None, 'alpha': None, 'pdp_per_row': None, 'xff': 0.5, 'ds': [], 'gamma': None, 'rra_num': None}]
            filename = /tmp/tmpQCLRj0
            start = 920804400
            step = 300
            values = []
            ds = [{'name': 'speed', 'min': 'U', 'max': 'U', 'unknown_sec': None, 'minimal_heartbeat': 600, 'value': None, 'rpn': None, 'type': 'COUNTER', 'last_ds': None}]
            ds[speed].name = speed
            ds[speed].min = U
            ds[speed].max = U
            ds[speed].minimal_heartbeat = 600
            ds[speed].type = COUNTER
            rra[0].rows = 24
            rra[0].cf = AVERAGE
            rra[0].steps = 1
            rra[0].xff = 0.5
            rra[0].ds = []
            rra[1].rows = 10
            rra[1].cf = AVERAGE
            rra[1].steps = 6
            rra[1].xff = 0.5
            rra[1].ds = []
            """.strip().split("\n")
        originalStdout = sys.stdout
        sys.stdout = StringIO()
        self.assertTrue(os.path.exists(self.rrdfile.name))
        self.rrd.info()
        for obtained, expected in zip(
            sys.stdout.getvalue().split("\n"), expectedOutput):
            if obtained.startswith("filename"):
                self.assertTrue(expected.strip().startswith("filename"))
            else:
                self.assertEquals(obtained.strip(), expected.strip())
        sys.stdout = originalStdout
