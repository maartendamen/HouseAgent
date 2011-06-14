import re
from datetime import datetime

from pyrrd import mapper
from pyrrd import util
from pyrrd.backend import external


def validateDSName(name):
    """
    >>> vname = validateDSName('Zaphod Beeble-Brox!')
    Traceback (most recent call last):
    ValueError: Names must consist only of the characters A-Z, a-z, 0-9, _
    >>> vname = validateDSName('Zaphod_Bee_Brox')
    >>> vname = validateDSName('a'*18)
    >>> vname = validateDSName('a'*19)
    Traceback (most recent call last):
    ValueError: Names must be shorter than 19 characters
    """
    if name != re.sub('[^A-Za-z0-9_]', '', name):
        raise ValueError, "Names must consist only of the characters " + \
            "A-Z, a-z, 0-9, _"
    if len(name) > 18:
        raise ValueError, "Names must be shorter than 19 characters"


def validateDSType(dsType):
    """
    >>> validateDSType('counter')
    'COUNTER'
    >>> validateDSType('ford prefect')
    Traceback (most recent call last):
    ValueError: A data source type must be one of the following: GAUGE COUNTER DERIVE ABSOLUTE COMPUTE
    """
    dsType = dsType.upper()
    valid = ['GAUGE', 'COUNTER', 'DERIVE', 'ABSOLUTE', 'COMPUTE']
    if dsType in valid:
        return dsType
    else:
        valid = ' '.join(valid)
        raise ValueError, 'A data source type must be one of the ' + \
            'following: %s' % valid


def validateRRACF(consolidationFunction):
    """
    >>> validateRRACF('Max')
    'MAX'
    >>> validateRRACF('Maximum')
    Traceback (most recent call last):
    ValueError: An RRA's consolidation function must be one of the following: AVERAGE MIN MAX LAST HWPREDICT SEASONAL DEVSEASONAL DEVPREDICT FAILURES
    >>> validateRRACF('Trisha MacMillan')
    Traceback (most recent call last):
    ValueError: An RRA's consolidation function must be one of the following: AVERAGE MIN MAX LAST HWPREDICT SEASONAL DEVSEASONAL DEVPREDICT FAILURES
    """
    cf = consolidationFunction.upper()
    valid = ['AVERAGE', 'MIN', 'MAX', 'LAST', 'HWPREDICT', 'SEASONAL',
             'DEVSEASONAL', 'DEVPREDICT', 'FAILURES']
    if cf in valid:
        return cf
    else:
        valid = ' '.join(valid)
        raise ValueError, "An RRA's consolidation function must be " + \
            "one of the following: %s" % valid


class RRD(mapper.RRDMapper):
    """
    >>> import os, tempfile
    >>>
    >>> dss = []
    >>> rras = []
    >>> rrdfile = tempfile.NamedTemporaryFile()
    >>> dss.append(DataSource(dsName='speed', dsType='COUNTER', heartbeat=600))
    >>> rras.append(RRA(cf='AVERAGE', xff=0.5, steps=1, rows=24))
    >>> rras.append(RRA(cf='AVERAGE', xff=0.5, steps=6, rows=10))
    >>> rrd = RRD(rrdfile.name, ds=dss, rra=rras, start=920804400)
    >>> rrd.create()
    >>> os.path.exists(rrdfile.name)
    True

    >>> rrd.bufferValue('920805600', '12363')
    >>> rrd.bufferValue('920805900', '12363')
    >>> rrd.bufferValue('920806200', '12373')
    >>> rrd.bufferValue('920806500', '12383')
    >>> rrd.update()
    >>> rrd.bufferValue('920806800', '12393')
    >>> rrd.bufferValue('920807100', '12399')
    >>> rrd.bufferValue('920807400', '12405')
    >>> rrd.bufferValue('920807700', '12411')
    >>> rrd.bufferValue('920808000', '12415')
    >>> rrd.bufferValue('920808300', '12420')
    >>> rrd.bufferValue('920808600', '12422')
    >>> rrd.bufferValue('920808900', '12423')
    >>> rrd.update()
    >>> len(rrd.values)
    0
    """
    def __init__(self, filename=None, start=None, step=300, ds=None, rra=None,
                 mode="w", backend=external):
        super(RRD, self).__init__()
        if filename == None:
            raise ValueError, "You must provide a filename."
        self.filename = filename
        if not start or isinstance(start, datetime):
            self.start = util.epoch(start)
        else:
            self.start = start
        if not ds:
            ds = []
        if not rra:
            rra = []
        self.ds = ds
        self.rra = rra
        self.values = []
        self.step = step
        self.lastupdate = None
        self.mode = mode
        # the backend attribute needs to be defined before the load call, since
        # the load method (super class) expects the backend attribute
        self.backend = backend
        if self.mode == "r":
            self.load()

    def bufferValue(self, timeOrData, *values):
        """
        The parameter 'values' can either be a an n-tuple, but it
        is assumed that the order in which the values are sent is
        the order in which they will be applied to the DSs (i.e.,
        respectively... i.e., in the order that the DSs were added
        to the RRD).

        >>> my_rrd = RRD('somefile')
        >>> my_rrd.bufferValue('1000000', 'value')
        >>> my_rrd.update(debug=True, dryRun=True)
        ('somefile', ['1000000:value'])
        >>> my_rrd.update(template='ds0', debug=True, dryRun=True)
        ('somefile', ['--template', 'ds0', '1000000:value'])
        >>> my_rrd.values = []

        >>> my_rrd.bufferValue('1000000:value')
        >>> my_rrd.update(debug=True, dryRun=True)
        ('somefile', ['1000000:value'])
        >>> my_rrd.update(template='ds0', debug=True, dryRun=True)
        ('somefile', ['--template', 'ds0', '1000000:value'])
        >>> my_rrd.values = []

        >>> my_rrd.bufferValue('1000000', 'value1', 'value2')
        >>> my_rrd.bufferValue('1000001', 'value3', 'value4')
        >>> my_rrd.update(debug=True, dryRun=True)
        ('somefile', ['1000000:value1:value2', '1000001:value3:value4'])
        >>> my_rrd.update(template='ds1:ds0', debug=True, dryRun=True)
        ('somefile', ['--template', 'ds1:ds0', '1000000:value1:value2', '1000001:value3:value4'])
        >>> my_rrd.values = []

        >>> my_rrd.bufferValue('1000000:value')
        >>> my_rrd.bufferValue('1000001:anothervalue')
        >>> my_rrd.update(debug=True, dryRun=True)
        ('somefile', ['1000000:value', '1000001:anothervalue'])
        >>> my_rrd.update(template='ds0', debug=True, dryRun=True)
        ('somefile', ['--template', 'ds0', '1000000:value', '1000001:anothervalue'])
        >>> my_rrd.values = []
        """
        values = ':'.join([ str(x) for x in values ])
        self.values.append((timeOrData, values))
        self.lastupdate = int(str(timeOrData).split(":")[0])

    # for backwards compatibility
    bufferValues = bufferValue

    def create(self, debug=False):
        data = self.backend.prepareObject('create', self)
        if debug:
            print data
        self.backend.create(*data)

    # XXX this can be uncommented when we're doing full database imports with
    # the loads method and storing those values in the python objects
    #def write(self, filename, debug=False):
    #    self.filename = filename
    #    if not os.path.exists(filename):
    #        self.create(debug)
    #    for rra in self.rra:
    #        for row in rra.database.rows:
    #            time, data =
    #            self.bufferValue(time, data)
    #        self.update()

    def update(self, debug=False, template=None, dryRun=False):
        """
        """
        # XXX this needs a lot more testing with different data
        # sources and values
        self.template = template
        if self.values:
            data = self.backend.prepareObject('update', self)
            if debug:
                print data
            if not dryRun:
                self.backend.update(debug=debug, *data)
                self.values = []

    def fetch(self, cf="AVERAGE", resolution=None, start=None, end=None,
              returnStyle="ds", useBindings=False):
        """
        By default, fetch returns a dict of data source names whose associated
        values are lists. The list for each DS contains (time, data) tuples.

        Optionally, one may pass returnStyle="time" and one will instead get a
        dict of times whose associated values are dicts. These associated dicts
        have a key for every defined DS and a corresponding value that is the
        data associated with that DS at the given time.

        # XXX add a doctest that creates an RRD with multiple DSs and RRAs
        """
        attributes = util.Attributes()
        attributes.filename = self.filename
        attributes.cf = cf
        attributes.resolution = resolution
        attributes.start = start
        attributes.end = end
        data = self.backend.prepareObject('fetch', attributes)
        if useBindings:
            kwds = {"useBindings": useBindings}
            return self.backend.fetch(*data, **kwds)
        print data
        return self.backend.fetch(*data)[returnStyle]

    def info(self, useBindings=False):
        """
        For this method, the info is rendered to stdout.
        """
        data = self.backend.prepareObject('info', self)
        kwds = {"useBindings": useBindings}
        self.backend.info(*data, **kwds)

    def load(self, filename=None, includeData=False):
        """
        # Create an empty file:
        >>> import os, tempfile
        >>>
        >>> dss = []
        >>> rras = []
        >>> rrdfile = tempfile.NamedTemporaryFile()
        >>> dss.append(DataSource(dsName='speed', dsType='COUNTER',
        ...   heartbeat=600))
        >>> rras.append(RRA(cf='AVERAGE', xff=0.5, steps=1, rows=24))
        >>> rras.append(RRA(cf='AVERAGE', xff=0.5, steps=6, rows=10))
        >>> rrd = RRD(rrdfile.name, ds=dss, rra=rras, start=920804400)
        >>> rrd.create()
        >>> os.path.exists(rrdfile.name)
        True

        # Add some values:
        >>> rrd.bufferValue('920805600', '12363')
        >>> rrd.bufferValue('920805900', '12363')
        >>> rrd.bufferValue('920806200', '12373')
        >>> rrd.bufferValue('920806500', '12383')
        >>> rrd.update()

        # Let's create another one, using the source file we just created. Note
        # that by passing the "read" mode, were letting the RRD class know that
        # it should call load() immediately, thus giving us read-access to the
        # file's data.
        >>> rrd2 = RRD(rrdfile.name, mode="r")

        # Now let's load the data from self.filename:
        >>> top_level_attrs = rrd2.getData()
        >>> top_level_attrs["lastupdate"]
        920806500
        >>> top_level_attrs["filename"] == rrdfile.name
        True
        >>> top_level_attrs["step"]
        300
        >>> len(rrd2.ds)
        1
        >>> len(rrd2.rra)
        2
        >>> sorted(rrd2.ds[0].getData().keys())
        ['last_ds', 'max', 'min', 'minimal_heartbeat', 'name', 'rpn', 'type', 'unknown_sec', 'value']
        >>> sorted(rrd2.rra[1].getData().keys())
        ['alpha', 'beta', 'cdp_prep', 'cf', 'database', 'ds', 'gamma', 'pdp_per_row', 'rows', 'rra_num', 'seasonal_period', 'steps', 'threshold', 'window_length', 'xff']

        # Finally, a comparison:
        >>> rrd.lastupdate == rrd2.lastupdate
        True
        >>> rrd.filename == rrd2.filename
        True
        >>> rrd.step == rrd2.step
        True

        """
        # XXX this should only be enabled once we have the data from the loaded
        # RRD file updating the RRD object
        #if filename:
        #    self.filename = filename

        # this re-maps all attributes of this object (self) based on what is
        # read in from self.filename
        self.map()

        # XXX add support for loading data from the database XML tag; when this
        # is implemented, we will also need to come up with the best way to
        # write this data back to disk (write the individual rows of data that
        # get read in, that is)
        if includeData:
            pass


class DataSource(mapper.DSMapper):
    """
    A single RRD can accept input from several data sources (DS),
    for example incoming and outgoing traffic on a specific
    communication line. With the DS configuration option you must
    define some basic properties of each data source you want to
    store in the RRD.

    ds-name is the name you will use to reference this particular
    data source from an RRD. A ds-name must be 1 to 19 characters
    long in the characters [a-zA-Z0-9_].

    DST defines the Data Source Type. The remaining arguments of a
    data source entry depend on the data source type. For GAUGE,
    COUNTER, DERIVE, and ABSOLUTE the format for a data source entry
    is:

        DS:ds-name:GAUGE | COUNTER | DERIVE | ABSOLUTE:heartbeat:min:max

    For COMPUTE data sources, the format is:

        DS:ds-name:COMPUTE:rpn-expression

    >>> ds = DataSource(dsName='speed', dsType='COUNTER', heartbeat=600)
    >>> ds
    DS:speed:COUNTER:600:U:U
    """
    def __init__(self, dsName=None, dsType=None, heartbeat=None, minval='U',
                 maxval='U', rpn=None):
        super(DataSource, self).__init__()
        if dsName == None:
            raise ValueError, "You must provide a name for the data source."
        if dsType == None:
            raise ValueError, "You must provide a type for the data source."
        self.name = dsName
        self.type = dsType
        self.minimal_heartbeat = heartbeat
        self.min = minval
        self.max = maxval
        self.rpn = rpn

    def __repr__(self):
        """
        We override this method for preparing the class's data for
        use with RRDTool.

        Time representations must have their ':'s escaped, since
        the colon is the RRDTool separator for parameters.
        """
        main = 'DS:%s:%s' % (self.name, self.type)
        tail = ''
        if self.type == 'COMPUTE':
            tail += ':%s' % self.rpn
        else:
            tail += ':%s:%s:%s' % (
                self.minimal_heartbeat, self.min, self.max)
        return main + tail


DS = DataSource


class RRA(mapper.RRAMapper):
    """
    The purpose of an RRD is to store data in the round robin
    archives (RRA). An archive consists of a number of data values
    or statistics for each of the defined data-sources (DS) and is
    defined with an RRA line.

    When data is entered into an RRD, it is first fit into time
    slots of the length defined with the -s option, thus becoming
    a primary data point.

    The data is also processed with the consolidation function (CF)
    of the archive. There are several consolidation functions that
    consolidate primary data points via an aggregate function:
    AVERAGE, MIN, MAX, LAST. The format of RRA line for these
    consolidation functions is:

        RRA:AVERAGE | MIN | MAX | LAST:xff:steps:rows

    xff The xfiles factor defines what part of a consolidation
    interval may be made up from *UNKNOWN* data while the consolidated
    value is still regarded as known.

    steps defines how many of these primary data points are used
    to build a consolidated data point which then goes into the
    archive.

    rows defines how many generations of data values are kept in
    an RRA.

    >>> rra1 = RRA(cf='AVERAGE', xff=0.5, steps=1, rows=24)
    >>> rra1
    RRA:AVERAGE:0.5:1:24
    >>> rra2 = RRA(cf='AVERAGE', xff=0.5, steps=6, rows=10)
    >>> rra2
    RRA:AVERAGE:0.5:6:10
    """
    def __init__(self, cf=None, xff=None, steps=None, rows=None, alpha=None,
                 beta=None, seasonal_period=None, rra_num=None, gamma=None,
                 threshold=None, window_length=None, cdpPrepObject=None,
                 databaseObject=None):
        super(RRA, self).__init__()
        if cf == None:
            msg = "You must provide a value for the consolidation function."
            raise ValueError, msg
        self.cf = cf
        self.xff = xff
        self.steps = steps
        self.rows = rows
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.seasonal_period = seasonal_period
        self.rra_num = rra_num
        self.threshold = threshold
        self.window_length = window_length
        # for object mapping
        self.cdp_prep = cdpPrepObject
        self.database = databaseObject

    def __repr__(self):
        """
        We override this method for preparing the class's data for
        use with RRDTool.

        Time representations must have their ':'s escaped, since
        the colon is the RRDTool separator for parameters.
        """
        main = 'RRA:%s' % self.cf
        tail = ''
        if self.cf in ['AVERAGE', 'MIN', 'MAX', 'LAST']:
            tail += ':%s:%s:%s' % (self.xff, self.steps, self.rows)
        elif self.cf == 'HWPREDICT':
            tail += ':%s:%s:%s' % (self.rows, self.alpha, self.beta)
            tail += ':%s:%s' % (self.seasonal_period, self.rra_num)
        elif self.cf == 'SEASONAL':
            tail += ':%s:%s:%s' % (
                self.seasonal_period, self.gamma, self.rra_num)
        elif self.cf == 'DEVSEASONAL':
            tail += ':%s:%s:%s' % (
                self.seasonal_period, self.gamma, self.rra_num)
        elif self.cf == 'DEVPREDICT':
            tail += ':%s:%s' % (self.rows, self.rra_num)
        elif self.cf == 'FAILURES':
            tail += ':%s:%s' % (self.rows, self.threshold)
            tail += ':%s:%s' % (self.window_length, self.rra_num)
        return main+tail


class Query(object):
    pass


if __name__ == '__main__':
    from doctest import testmod
    testmod()
