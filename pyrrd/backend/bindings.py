"""
The following exercises the RRD class with this backend:

Create an RRD file programmatically::

    >>> import tempfile
    >>> from pyrrd.rrd import DataSource, RRA, RRD
    >>> from pyrrd.backend import bindings

    >>> rrdfile = tempfile.NamedTemporaryFile()
    >>> dataSources = []
    >>> roundRobinArchives = []
    >>> dataSource = DataSource(
    ...     dsName='speed', dsType='COUNTER', heartbeat=600)
    >>> dataSources.append(dataSource)
    >>> roundRobinArchives.append(RRA(cf='AVERAGE', xff=0.5, steps=1, rows=24))
    >>> roundRobinArchives.append(RRA(cf='AVERAGE', xff=0.5, steps=6, rows=10))

    >>> myRRD = RRD(rrdfile.name, ds=dataSources, rra=roundRobinArchives, 
    ...     start=920804400, backend=bindings)
    >>> myRRD.create()

Let's check to see that the file exists::

    >>> import os
    >>> os.path.isfile(rrdfile.name)
    True

Let's see how big it is::

    >>> bytes = len(open(rrdfile.name).read())
    >>> 800 < bytes < 1200
    True

In order to save writes to disk, PyRRD buffers values and then writes the
values to the RRD file at one go::

    >>> myRRD.bufferValue('920805600', '12363')
    >>> myRRD.bufferValue('920805900', '12363')
    >>> myRRD.bufferValue('920806200', '12373')
    >>> myRRD.bufferValue('920806500', '12383')
    >>> myRRD.update()

Let's add some more data::

    >>> myRRD.bufferValue('920806800', '12393')
    >>> myRRD.bufferValue('920807100', '12399')
    >>> myRRD.bufferValue('920807400', '12405')
    >>> myRRD.bufferValue('920807700', '12411')
    >>> myRRD.bufferValue('920808000', '12415')
    >>> myRRD.bufferValue('920808300', '12420')
    >>> myRRD.bufferValue('920808600', '12422')
    >>> myRRD.bufferValue('920808900', '12423')
    >>> myRRD.update()

Info checks when the RRD object is in write mode::

    >>> myRRD.info() # doctest:+ELLIPSIS
    lastupdate = 920808900
    rra = [{'rows': 24, 'database': None, 'cf': 'AVERAGE', 'cdp_prep': None, 'beta': None, 'seasonal_period': None, 'steps': 1, 'window_length': None, 'threshold': None, 'alpha': None, 'pdp_per_row': None, 'xff': 0.5, 'ds': [], 'gamma': None, 'rra_num': None}, {'rows': 10, 'database': None, 'cf': 'AVERAGE', 'cdp_prep': None, 'beta': None, 'seasonal_period': None, 'steps': 6, 'window_length': None, 'threshold': None, 'alpha': None, 'pdp_per_row': None, 'xff': 0.5, 'ds': [], 'gamma': None, 'rra_num': None}]
    filename = /tmp/...
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

Info checks when the RRD object is in read mode::

    >>> myRRD2 = RRD(rrdfile.name, mode="r")
    >>> myRRD2.info() # doctest:+ELLIPSIS
    lastupdate = 920808900
    rra = [{'rows': None, 'database': None, 'cf': 'AVERAGE', 'cdp_prep': None, 'beta': None, 'seasonal_period': None, 'steps': None, 'window_length': None, 'threshold': None, 'alpha': None, 'pdp_per_row': 1, 'xff': 0.5, 'ds': [{'unknown_datapoints': 0, 'secondary_value': nan, 'primary_value': 0.0033333333333, 'value': nan}], 'gamma': None, 'rra_num': None}, {'rows': None, 'database': None, 'cf': 'AVERAGE', 'cdp_prep': None, 'beta': None, 'seasonal_period': None, 'steps': None, 'window_length': None, 'threshold': None, 'alpha': None, 'pdp_per_row': 6, 'xff': 0.5, 'ds': [{'unknown_datapoints': 0, 'secondary_value': 0.013333333333, 'primary_value': 0.023333333333, 'value': 0.026666666666999999}], 'gamma': None, 'rra_num': None}]
    filename = /tmp/...
    start = ...
    step = 300
    version = 3
    values = []
    ds = [{'name': 'speed', 'min': 'NaN', 'max': 'NaN', 'unknown_sec': 0, 'minimal_heartbeat': 600, 'value': 0.0, 'rpn': None, 'type': 'COUNTER', 'last_ds': 12423}]
    ds[speed].name = speed
    ds[speed].min = NaN
    ds[speed].max = NaN
    ds[speed].unknown_sec = 0
    ds[speed].minimal_heartbeat = 600
    ds[speed].value = 0.0
    ds[speed].type = COUNTER
    ds[speed].last_ds = 12423
    rra[0].cf = AVERAGE
    rra[0].pdp_per_row = 1
    rra[0].xff = 0.5
    rra[0].ds = [{'unknown_datapoints': 0, 'secondary_value': nan, 'primary_value': 0.0033333333333, 'value': nan}]
    rra[0].cdp_prep[0].unknown_datapoints = 0
    rra[0].cdp_prep[0].secondary_value = nan
    rra[0].cdp_prep[0].primary_value = 0.0033333333333
    rra[0].cdp_prep[0].value = nan
    rra[1].cf = AVERAGE
    rra[1].pdp_per_row = 6
    rra[1].xff = 0.5
    rra[1].ds = [{'unknown_datapoints': 0, 'secondary_value': 0.013333333333, 'primary_value': 0.023333333333, 'value': 0.026666666666999999}]
    rra[1].cdp_prep[0].unknown_datapoints = 0
    rra[1].cdp_prep[0].secondary_value = 0.013333333333
    rra[1].cdp_prep[0].primary_value = 0.023333333333
    rra[1].cdp_prep[0].value = 0.026666666667

    >>> myRRD.info(useBindings=True) # doctest:+ELLIPSIS
    {'ds': {'speed': {'ds_name': 'speed',
                      'last_ds': '12423',
                      'max': None,
                      'min': None,
                      'minimal_heartbeat': 600,
                      'type': 'COUNTER',
                      'unknown_sec': 0,
                      'value': 0.0}},
     'filename': '/tmp/...
     'last_update': 920808900,
     'rra': [{'cdp_prep': [{'unknown_datapoints': 0, 'value': None}],
              'cf': 'AVERAGE',
              'pdp_per_row': 1,
              'rows': 24,
              'xff': 0.5},
             {'cdp_prep': [{'unknown_datapoints': 0,
                            'value': 0.026666666666666668}],
              'cf': 'AVERAGE',
              'pdp_per_row': 6,
              'rows': 10,
              'xff': 0.5}],
     'rrd_version': '0003',
     'step': 300}

In order to create a graph, we'll need some data definitions. We'll also
throw in some calculated definitions and variable definitions for good
meansure::

    >>> from pyrrd.graph import DEF, CDEF, VDEF, LINE, AREA, GPRINT
    >>> def1 = DEF(rrdfile=myRRD.filename, vname='myspeed',
    ...     dsName=dataSource.name)
    >>> cdef1 = CDEF(vname='kmh', rpn='%s,3600,*' % def1.vname)
    >>> cdef2 = CDEF(vname='fast', rpn='kmh,100,GT,kmh,0,IF')
    >>> cdef3 = CDEF(vname='good', rpn='kmh,100,GT,0,kmh,IF')
    >>> vdef1 = VDEF(vname='mymax', rpn='%s,MAXIMUM' % def1.vname)
    >>> vdef2 = VDEF(vname='myavg', rpn='%s,AVERAGE' % def1.vname)

    >>> line1 = LINE(value=100, color='#990000', legend='Maximum Allowed')
    >>> area1 = AREA(defObj=cdef3, color='#006600', legend='Good Speed')
    >>> area2 = AREA(defObj=cdef2, color='#CC6633', legend='Too Fast')
    >>> line2 = LINE(defObj=vdef2, color='#000099', legend='My Average', 
    ...     stack=True)
    >>> gprint1 = GPRINT(vdef2, '%6.2lf kph')

Color is the spice of life. Let's spice it up a little::

    >>> from pyrrd.graph import ColorAttributes
    >>> ca = ColorAttributes()
    >>> ca.back = '#333333'
    >>> ca.canvas = '#333333'
    >>> ca.shadea = '#000000'
    >>> ca.shadeb = '#111111'
    >>> ca.mgrid = '#CCCCCC'
    >>> ca.axis = '#FFFFFF'
    >>> ca.frame = '#AAAAAA'
    >>> ca.font = '#FFFFFF'
    >>> ca.arrow = '#FFFFFF'

Now we can create a graph for the data in our RRD file::

    >>> from pyrrd.graph import Graph
    >>> graphfile = tempfile.NamedTemporaryFile(suffix=".png")
    >>> g = Graph(graphfile.name, start=920805000, end=920810000,
    ...     vertical_label='km/h', color=ca, backend=bindings)
    >>> g.data.extend([def1, cdef1, cdef2, cdef3, vdef1, vdef2, line1, area1,
    ...     area2, line2, gprint1])
    >>> g.write()

Let's make sure it's there::

    >>> os.path.isfile(graphfile.name)
    True

Let's see how big it is::

    >>> bytes = len(open(graphfile.name).read())
    >>> 10300 < bytes < 10700
    True

Open that up in your favorite image browser and confirm that the appropriate
RRD graph is generated.
"""
import rrdtool

from pyrrd.backend import external
from pyrrd.backend.common import buildParameters


def _cmd(command, args):
    function = getattr(rrdtool, command)
    return function(*args)


def create(filename, parameters):
    """
    >>> rrdfile = '/tmp/test.rrd'
    >>> parameters = [
    ...   '--start',
    ...   '920804400',
    ...   'DS:speed:COUNTER:600:U:U',
    ...   'RRA:AVERAGE:0.5:1:24',
    ...   'RRA:AVERAGE:0.5:6:10']
    >>> create(rrdfile, parameters)

    # Check that the file's there:
    >>> import os
    >>> os.path.exists(rrdfile)
    True

    # Cleanup:
    >>> os.unlink(rrdfile)
    >>> os.path.exists(rrdfile)
    False
    """
    parameters.insert(0, filename)
    output = _cmd('create', parameters)


def update(filename, parameters, debug=False):
    """
    >>> rrdfile = '/tmp/test.rrd'
    >>> parameters = [
    ...   '--start',
    ...   '920804400',
    ...   'DS:speed:COUNTER:600:U:U',
    ...   'RRA:AVERAGE:0.5:1:24',
    ...   'RRA:AVERAGE:0.5:6:10']
    >>> create(rrdfile, parameters)

    >>> import os
    >>> os.path.exists(rrdfile)
    True

    >>> parameters = ['920804700:12345', '920805000:12357', '920805300:12363']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920805600:12363', '920805900:12363','920806200:12373']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920806500:12383', '920806800:12393','920807100:12399']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920807400:12405', '920807700:12411', '920808000:12415']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920808300:12420', '920808600:12422','920808900:12423']
    >>> update(rrdfile, parameters)

    >>> os.unlink(rrdfile)
    >>> os.path.exists(rrdfile)
    False
    """
    parameters.insert(0, filename)
    if debug:
        _cmd('updatev', parameters)
    else:
        _cmd('update', parameters)


def fetch(filename, parameters, useBindings=False):
    """
    By default, this function does not use the bindings for fetch. The reason
    for this is we want default compatibility with the data output/results from
    the fetch method for both the external and bindings modules.

    If a developer really wants to use the native bindings to get the fetch
    data, they may do so by explicitly setting the useBindings parameter. This
    will return data in the Python Python bindings format, though.

    Do be aware, though, that the PyRRD format is much easier to get data out
    of in a sensible manner (unless you really like the RRDTool approach).

    >>> rrdfile = '/tmp/test.rrd'
    >>> parameters = [
    ...   '--start',
    ...   '920804400',
    ...   'DS:speed:COUNTER:600:U:U',
    ...   'RRA:AVERAGE:0.5:1:24',
    ...   'RRA:AVERAGE:0.5:6:10']
    >>> create(rrdfile, parameters)

    >>> import os
    >>> os.path.exists(rrdfile)
    True

    >>> parameters = ['920804700:12345', '920805000:12357', '920805300:12363']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920805600:12363', '920805900:12363','920806200:12373']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920806500:12383', '920806800:12393','920807100:12399']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920807400:12405', '920807700:12411', '920808000:12415']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920808300:12420', '920808600:12422','920808900:12423']
    >>> update(rrdfile, parameters)

    >>> parameters = ['AVERAGE', '--start', '920804400', '--end', '920809200']
    >>> results = fetch(rrdfile, parameters, useBindings=True)

    >>> results[0]
    (920804400, 920809500, 300)
    >>> results[1]
    ('speed',)
    >>> len(results[2])
    18

    # For more info on the PyRRD data format, see the docstring for
    # pyrrd.external.fetch.
    >>> parameters = ['AVERAGE', '--start', '920804400', '--end', '920809200']
    >>> results = fetch(rrdfile, parameters, useBindings=False)
    >>> sorted(results["ds"].keys())
    ['speed']
    
    >>> os.unlink(rrdfile)
    >>> os.path.exists(rrdfile)
    False
    """
    if useBindings:
        parameters.insert(0, filename)
        return _cmd('fetch', parameters)
    else:
        return external.fetch(filename, " ".join(parameters))


def dump(filename, outfile="", parameters=[]):
    """
    The rrdtool Python bindings don't have support for dump, so we need to use
    the external dump function.

    >>> rrdfile = '/tmp/test.rrd'
    >>> parameters = [
    ...   '--start',
    ...   '920804400',
    ...   'DS:speed:COUNTER:600:U:U',
    ...   'RRA:AVERAGE:0.5:1:24',
    ...   'RRA:AVERAGE:0.5:6:10']
    >>> create(rrdfile, parameters)

    >>> xml = dump(rrdfile)
    >>> xmlBytes = len(xml)
    >>> 3300 < xmlBytes < 4000
    True
    >>> xmlCommentCheck = '<!-- Round Robin Database Dump'
    >>> xmlCommentCheck in xml[0:200]
    True

    >>> xmlfile = '/tmp/test.xml'
    >>> dump(rrdfile, xmlfile)

    >>> import os
    >>> os.path.exists(xmlfile)
    True

    >>> os.unlink(rrdfile)
    >>> os.unlink(xmlfile)
    """
    parameters = " ".join(parameters)
    output = external.dump(filename, outfile, parameters)
    if output:
        return output.strip()


def load(filename):
    """
    The rrdtool Python bindings don't have support for load, so we need to use
    the external load function.

    >>> rrdfile = '/tmp/test.rrd'
    >>> parameters = [
    ...   '--start',
    ...   '920804400',
    ...   'DS:speed:COUNTER:600:U:U',
    ...   'RRA:AVERAGE:0.5:1:24',
    ...   'RRA:AVERAGE:0.5:6:10']
    >>> create(rrdfile, parameters)

    >>> tree = load(rrdfile)
    >>> [x.tag for x in tree]
    ['version', 'step', 'lastupdate', 'ds', 'rra', 'rra']
    """
    return external.load(filename)


def info(filename, obj=None, useBindings=False):
    """
    Similarly to the fetch function, the info function uses
    pyrrd.backend.external by default. This is due to the fact that 1) the
    output of the RRD info module is much more easily legible, and 2) it is
    very similar in form to the output produced by the "rrdtool info" command.
    The output produced by the rrdtool Python bindings is a data structure and
    more difficult to view.

    However, if that output is what you desire, then simply set the useBindings
    parameter to True.
    """
    if useBindings:
        from pprint import pprint
        pprint(_cmd('info', [filename]))
    else:
        external.info(filename, obj)


def graph(filename, parameters):
    """
    >>> import tempfile
    >>>
    >>> rrdfile = '/tmp/test.rrd'
    >>> parameters = [
    ...   '--start',
    ...   '920804400',
    ...   'DS:speed:COUNTER:600:U:U',
    ...   'RRA:AVERAGE:0.5:1:24',
    ...   'RRA:AVERAGE:0.5:6:10']
    >>> create(rrdfile, parameters)

    >>> import os
    >>> os.path.exists(rrdfile)
    True

    >>> parameters = ['920804700:12345', '920805000:12357', '920805300:12363']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920805600:12363', '920805900:12363','920806200:12373']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920806500:12383', '920806800:12393','920807100:12399']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920807400:12405', '920807700:12411', '920808000:12415']
    >>> update(rrdfile, parameters)
    >>> parameters = ['920808300:12420', '920808600:12422','920808900:12423']
    >>> update(rrdfile, parameters)

    >>> parameters = [
    ...   '--start',
    ...   '920804400', 
    ...   '--end', 
    ...   '920808000',
    ...   '--vertical-label',
    ...   'km/h',
    ...   'DEF:myspeed=%s:speed:AVERAGE' % rrdfile,
    ...   'CDEF:realspeed=myspeed,1000,*',
    ...   'CDEF:kmh=myspeed,3600,*',
    ...   'CDEF:fast=kmh,100,GT,kmh,0,IF',
    ...   'CDEF:good=kmh,100,GT,0,kmh,IF',
    ...   'HRULE:100#0000FF:"Maximum allowed"',
    ...   'AREA:good#00FF00:"Good speed"',
    ...   'AREA:fast#00FFFF:"Too fast"',
    ...   'LINE2:realspeed#FF0000:Unadjusted']
    >>> graphfile = tempfile.NamedTemporaryFile()
    >>> graph(graphfile.name, parameters)

    >>> os.path.exists(graphfile.name)
    True

    """
    parameters.insert(0, filename)
    output = _cmd('graph', parameters)


def prepareObject(function, obj):
    """
    This is a funtion that serves to make interacting with the
    backend as transparent as possible. It"s sole purpose it to
    prepare the attributes and data of the various pyrrd objects
    for use by the functions that call out to rrdtool.

    For all of the rrdtool-methods in this module, we need to split
    the named parameters up into pairs, assebled all the stuff in
    the list obj.data, etc.

    This function will get called by methods in the pyrrd wrapper
    objects. For instance, most of the methods of pyrrd.rrd.RRD
    will call this function. In graph, Pretty much only the method
    pyrrd.graph.Graph.write() will call this function.
    """
    if function == 'create':
        validParams = ['start', 'step']
        params = buildParameters(obj, validParams)
        params += [str(x) for x in obj.ds]
        params += [str(x) for x in obj.rra]
        return (obj.filename, params)

    if function == 'update':
        validParams = ['template']
        params = buildParameters(obj, validParams)
        FIRST_VALUE = 0
        DATA = 1
        TIME_OR_DATA = 0
        if obj.values[FIRST_VALUE][DATA]:
            params += ['%s:%s' % (time, values) for time, values in obj.values]
        else:
            params += [data for data, nil in obj.values]
        return (obj.filename, params)

    if function == 'fetch':
        validParams = ['resolution', 'start', 'end']
        params = buildParameters(obj, validParams)
        params.insert(0, obj.cf)
        return (obj.filename, params)

    if function == 'info':
        return (obj.filename, obj)

    if function == 'graph':
        validParams = ['start', 'end', 'step', 'title',
            'vertical_label', 'width', 'height', 'only_graph',
            'upper_limit', 'lower_limit', 'rigid', 'alt_autoscale',
            'alt_autoscale_max', 'no_gridfit', 'x_grid', 'y_grid',
            'alt_y_grid', 'logarithmic', 'units_exponent', 'zoom',
            'font', 'font_render_mode', 'interlaced', 'no_legend',
            'force_rules_legend', 'tabwidth', 'base', 'color']
        params = buildParameters(obj, validParams)
        params += [str(x) for x in obj.data]
        return (obj.filename, params)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
