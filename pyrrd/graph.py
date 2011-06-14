import os
import re

from pyrrd.backend import external

def validateVName(name):
    '''
    RRDTool vnames must be made up strings of the following characters:
         A-Z, a-z, 0-9, -,_
    and have a maximum length of 255 characters.

    >>> vname = validateVName('Zaphod Beeble-Brox!')
    Traceback (most recent call last):
    ValueError: Names must consist only of the characters A-Z, a-z, 0-9, -, _
    >>> vname = validateVName('Zaphod_Beeble-Brox')
    >>> vname = validateVName('a'*32)
    >>> vname = validateVName('a'*254)
    >>> vname = validateVName('a'*255)
    >>> vname = validateVName('a'*256)
    Traceback (most recent call last):
    ValueError: Names must be shorter than 255 characters
    '''
    if name != re.sub('[^A-Za-z0-9_-]', '', name):
        raise ValueError, "Names must consist only of the characters " + \
            "A-Z, a-z, 0-9, -, _"
    if len(name) > 255:
        raise ValueError, "Names must be shorter than 255 characters"
    return name

def escapeColons(data):
    '''
    Time data in RRD parameters that have colons need to escape
    them, due to the fact that RRDTool uses colons as separators.

    Additionally, comments have to be colon-escaped as well.

    >>> print escapeColons('now')
    now
    >>> print escapeColons('end-8days8hours')
    end-8days8hours
    >>> print escapeColons('13:00')
    13\:00
    '''
    return re.sub(':', '\:', data)

def validateObjectType(instance, objType):
    '''
    >>> my_list = [1,2,3,4,5]
    >>> validateObjectType(my_list, list)
    [1, 2, 3, 4, 5]
    >>> validateObjectType(my_list, dict)
    Traceback (most recent call last):
    TypeError: list instance is not of type dict
    '''
    if isinstance(instance, objType):
        return instance
    raise TypeError, "%s instance is not of type %s" % (
        type(instance).__name__, objType.__name__)

def validateImageFormat(format):
    '''
    >>> validateImageFormat('txt')
    Traceback (most recent call last):
    ValueError: The image format must be one of the following: PNG SVG EPS PDF
    >>> validateImageFormat('jpg')
    Traceback (most recent call last):
    ValueError: The image format must be one of the following: PNG SVG EPS PDF
    >>> validateImageFormat('png')
    'PNG'
    '''
    format = format.upper()
    valid = ['PNG', 'SVG', 'EPS', 'PDF']
    if format in valid:
        return format
    else:
        valid = ' '.join(valid)
        raise ValueError, 'The image format must be one of the ' + \
            'following: %s' % valid

class DataDefinition(object):
    '''
    This object causes data to be fetched from the RRD file. The
    virtual name vname can then be used throughout the rest of the
    script. By default, an RRA which contains the correct consolidated
    data at an appropriate resolution will be chosen. The resolution
    can be overridden with the --step option. The resolution can
    again be overridden by specifying the step size. The time span
    of this data is the same as for the graph by default, you can
    override this by specifying start and end. Remember to escape
    colons in the time specification!

    If the resolution of the data is higher than the resolution of
    the graph, the data will be further consolidated. This may
    result in a graph that spans slightly more time than requested.
    Ideally each point in the graph should correspond with one CDP
    from an RRA. For instance, if your RRD has an RRA with a
    resolution of 1800 seconds per CDP, you should create an image
    with width 400 and time span 400*1800 seconds (use appropriate
    start and end times, such as --start end-8days8hours).

    If consolidation needs to be done, the CF of the RRA specified
    in the DEF itself will be used to reduce the data density. This
    behaviour can be changed using :reduce=<CF>. This optional
    parameter specifies the CF to use during the data reduction
    phase.

    >>> def1 = DataDefinition(vname='ds0a',
    ...   rrdfile='/home/rrdtool/data/router1.rrd', dsName='ds0',
    ...   cdef='AVERAGE')
    >>> def1
    DEF:ds0a=/home/rrdtool/data/router1.rrd:ds0:AVERAGE
    >>> def1.__repr__()
    'DEF:ds0a=/home/rrdtool/data/router1.rrd:ds0:AVERAGE'

    >>> def2 = DataDefinition(rrdfile='/home/rrdtool/data/router1.rrd')
    >>> def2.vname = 'ds0b'
    >>> def2.dsName = 'ds0'
    >>> def2.cdef = 'AVERAGE'
    >>> def2.step = 1800
    >>> def2
    DEF:ds0b=/home/rrdtool/data/router1.rrd:ds0:AVERAGE:step=1800

    >>> def3 = DEF(vname='ds0c', dsName='ds0', step=7200)
    >>> def3.rrdfile = '/home/rrdtool/data/router1.rrd'
    >>> def3
    DEF:ds0c=/home/rrdtool/data/router1.rrd:ds0:AVERAGE:step=7200
    >>> def4 = DEF()
    >>> def4
    Traceback (most recent call last):
    ValueError: vname, rrdfile, dsName, and cdef are all required attributes and cannot be None.
    >>> def4.rrdfile = '/home/rrdtool/data/router2.rrd'
    >>> def4
    Traceback (most recent call last):
    ValueError: vname, rrdfile, dsName, and cdef are all required attributes and cannot be None.
    >>> def4.vname = 'ds1a'
    >>> def4
    Traceback (most recent call last):
    ValueError: vname, rrdfile, dsName, and cdef are all required attributes and cannot be None.
    >>> def4.dsName = 'ds1'
    >>> def4
    DEF:ds1a=/home/rrdtool/data/router2.rrd:ds1:AVERAGE
    '''
    def __init__(self, vname='', rrdfile='', dsName='', cdef='AVERAGE',
        step=None, start=None, end=None, reduce=None):
        self.vname = validateVName(vname)
        self.rrdfile = escapeColons(rrdfile)
        self.dsName = dsName
        self.cdef = cdef
        self.step = step
        self.start = start
        self.end = end
        self.reduce = reduce

    def __repr__(self):
        '''
        We override this method for preparing the class's data for use with
        RRDTool.

        Time representations must have their ':'s escaped, since the colon is
        the RRDTool separator for parameters.
        '''
        if not (self.vname and self.rrdfile and self.dsName and
            self.cdef):
            msg = ("vname, rrdfile, dsName, and cdef " +
                "are all required attributes and cannot be None.")
            raise ValueError, msg
        main = 'DEF:%(vname)s=%(rrdfile)s:%(dsName)s:%(cdef)s' % (
            self.__dict__)
        tail = ''
        if self.step:
            tail += ':step=%s' % self.step
        if self.start:
            tail += ':start=%s' % escapeColons(self.start)
        if self.end:
            tail += ':end=%s' % escapeColons(self.end)
        if self.reduce:
            tail += ':reduce=%s' % self.reduce
        return main+tail

DEF = DataDefinition

class VariableDefinition(object):
    '''
    This object has two attributes:
        vname
        rpn_expr

    It generates a value and/or a time according to the RPN
    statements used. The resulting vname will, depending on the
    functions used, have a value and a time component. When you use
    this vname in another RPN expression, you are effectively
    inserting its value just as if you had put a number at that
    place. The variable can also be used in the various graph and
    print elements.

    Note that currently only agregation functions work in VDEF rpn
    expressions (a limitation of RRDTool, not PyRRD).

    >>> def1 = DEF(rrdfile='/home/rrdtool/data/router1.rrd',
    ...   vname='ds0a', dsName='ds0')
    >>> def2 = DEF(rrdfile='/home/rrdtool/data/router1.rrd',
    ...   vname='ds1a', dsName='ds1')
    >>> rpnmax = '%s,MAXIMUM'
    >>> rpnmin = '%s,MINIMUM'
    >>> rpnavg = '%s,AVERAGE'
    >>> rpnpct = '%s,%s,PERCENT'
    >>> vdef1 = VariableDefinition(vname='ds0max',
    ...   rpn=rpnmax % def1.dsName)
    >>> vdef1
    VDEF:ds0max=ds0,MAXIMUM
    >>> vdef2 = VDEF(vname='ds0avg', rpn=rpnavg % def1.dsName)
    >>> vdef2
    VDEF:ds0avg=ds0,AVERAGE
    >>> vdef3 = VDEF(vname='ds0min', rpn=rpnmin % def1.dsName)
    >>> vdef3
    VDEF:ds0min=ds0,MINIMUM
    >>> vdef4 = VDEF(vname='ds1pct', rpn=rpnpct % (def2.dsName, 95))
    >>> vdef4
    VDEF:ds1pct=ds1,95,PERCENT
    '''
    def __init__(self, vname=None, rpn=None):
        if vname == None:
            raise ValueError, "You must provide a variable definition name."
        if rpn == None:
            raise ValueError, "You must provide an RPN statement(s)."
        self.vname = validateVName(vname)
        self.rpn = rpn
        self.abbr = 'VDEF'

    def __repr__(self):
        '''
    We override this method for preparing the class's data for
    use with RRDTool.

        Time representations must have their ':'s escaped, since
        the colon is the RRDTool separator for parameters.
        '''
        main = self.abbr+':%(vname)s=%(rpn)s' % (
            self.__dict__)
        return main

VDEF = VariableDefinition

class CalculationDefinition(VariableDefinition):
    '''
    This object creates a new set of data points (in memory only,
    not in the RRD file) out of one or more other data series.

    It has two attributes:
        vname
        rpn_expr

    The RPN instructions are used to evaluate a mathematical function
    on each data point. The resulting vname can then be used further
    on in the script, just as if it were generated by a DEF
    instruction.

    >>> someDSN = 'mydata'
    >>> cdef1 = CDEF(vname='mydatabits', rpn='%s,8,*' % someDSN)
    >>> cdef1
    CDEF:mydatabits=mydata,8,*
    '''
    def __init__(self, vname=None, rpn=None):
        super(CalculationDefinition, self).__init__(vname, rpn)
        self.abbr = 'CDEF'

CDEF = CalculationDefinition

class Print(object):
    '''
    Depending on the context, either the value component or the
    time component of a VDEF is printed using format. It is an error
    to specify a vname generated by a DEF or CDEF.

    Any text in format is printed literally with one exception: The
    percent character introduces a formatter string. This string
    can be:

    For printing values:

        %% just prints a literal '%' character

    %#.#le prints numbers like 1.2346e+04. The optional integers
    # denote field width and decimal precision.

    %#.#lf prints numbers like 12345.6789, with optional field
    width and precision.

    %s place this after %le, %lf or %lg. This will be replaced
    by the appropriate SI magnitude unit and the value will be
    scaled accordingly (123456 -> 123.456 k).

    %S is similar to %s. It does, however, use a previously
    defined magnitude unit. If there is no such unit yet, it
    tries to define one (just like %s) unless the value is zero,
    in which case the magnitude unit stays undefined. Thus,
    formatter strings using %S and no %s will all use the same
    magnitude unit except for zero values.

    For printing times:

        %% just prints a literal '%' character

    %a, %A print the abbreviated or full name of the day of the
    week.

        %b, %B print the abbreviated or full name of the month.

    %d, %m, %y, %H, %M, %S print day, month, year, hour, minute,
    and second in two-digit format.

        %Y prints the year in 4-digit format.

        %I, %p print the hour (01..12), 'am' or 'pm'.

        %j, %w print day of the week (0..6), day of the year (1..366)

        %c, %x, %X print date+time, date only, time only.

    %U, %W number of the week of the current year, with either
    the first Sunday (%U) or the first Monday (%W) determining
    the first week.

        %Z prints the time zone.

    This object takes as parameters:
        a VDEF instance
        a format, per defined above

    This is for printing to stdout. See GraphPrint for printing to
    the generated graphs.

    >>> def1 = DEF(rrdfile='/home/rrdtool/data/router1.rrd',
    ...   vname='ds0a', dsName='ds0')
    >>> vdef1 = VariableDefinition(vname='ds0max',
    ...   rpn='%s,MAXIMUM' % def1.dsName)
    >>> prnFmt = "%6.2lf %Sbps"
    >>> prn = Print(vdef1, prnFmt)
    >>> prn
    PRINT:ds0max:"%6.2lf %Sbps"
    '''
    def __init__(self, vdefObj, format):
        vdefObj = validateObjectType(vdefObj, VariableDefinition)
        self.vname = vdefObj.vname
        self.format = format
        self.abbr = 'PRINT'

    def __repr__(self):
        '''
    We override this method for preparing the class's data for
    use with RRDTool.

        Time representations must have their ':'s escaped, since
        the colon is the RRDTool separator for parameters.
        '''
        main = self.abbr+':%s:"%s"' % (self.vname, escapeColons(self.format))
        return main

PRINT = Print

class GraphPrint(Print):
    '''
    This is the same as PRINT, but printed inside the graph.

    >>> def1 = DEF(rrdfile='/home/rrdtool/data/router1.rrd',
    ...   vname='ds0a', dsName='ds0')
    >>> vdef1 = VariableDefinition(vname='ds0max',
    ...   rpn='%s,MAXIMUM' % def1.dsName)
    >>> prnFmt = '%6.2lf %Sbps'
    >>> prn = GraphPrint(vdef1, prnFmt)
    >>> prn
    GPRINT:ds0max:"%6.2lf %Sbps"
    '''
    def __init__(self, vdefObj, format):
        super(GraphPrint, self).__init__(vdefObj, format)
        self.abbr = 'GPRINT'

GPRINT = GraphPrint

class GraphComment(object):
    '''
    Text is printed literally in the legend section of the graph.
    Note that in RRDtool 1.2 you have to escape colons in COMMENT
    text in the same way you have to escape them in *PRINT commands
    by writing '\:'.

    >>> cmt = GraphComment('95th percentile')
    >>> len(str(cmt))
    26
    >>> cmt = GraphComment('95th percentile', autoNewline=False)
    >>> len(str(cmt))
    25
    >>> print cmt
    COMMENT:"95th percentile"
    '''
    def __init__(self, comment, autoNewline=True):
        self.autoNewline = autoNewline
        self.comment = comment

    def __repr__(self):
        '''
        We override this method for preparing the class's data for
        use with RRDTool.

        Time representations must have their ':'s escaped, since
        the colon is the RRDTool separator for parameters.
        '''
        newLine = '\n'
        if not self.autoNewline:
            newLine = ''
        main = 'COMMENT:"%s"%s' % ( self.comment, newLine)
        return main

COMMENT = GraphComment

class GraphVerticalLine(object):
    '''
    Draw a vertical line at time. Its color is composed from three
    hexadecimal numbers specifying the rgb color components (00 is
    off, FF is maximum) red, green and blue. Optionally, a legend
    box and string is printed in the legend section. time may be a
    number or a variable from a VDEF. It is an error to use vnames
    from DEF or CDEF here.
    '''
    # XXX TODO
VRULE = GraphVerticalLine

class Line(object):
    '''
    Draw a line of the specified width onto the graph.

    Width can be a floating point number. If the color is not
    specified, the drawing is done 'invisibly'. This is useful when
    stacking something else on top of this line.

    Also optional is the legend box and string which will be printed
    in the legend section if specified.

    The value can be generated by DEF, VDEF, and CDEF.  If the
    optional STACK modifier is used, this line is stacked on top
    of the previous element which can be a LINE or an AREA.

    When you do not specify a color, you cannot specify a legend.
    Should you want to use STACK, use the ``LINEx:<value>::STACK''
    form.

    >>> def1 = DEF(rrdfile='/home/rrdtool/data/router1.rrd',
    ...   vname='ds0a', dsName='ds0')
    >>> vdef1 = VariableDefinition(vname='ds0max',
    ...   rpn='%s,MAXIMUM' % def1.dsName)

    # Now let's do some lines...
    >>> line = Line(1, value='ds0max', color='#00ff00',
    ...   legend="Max")
    >>> line
    LINE1:ds0max#00ff00:"Max"
    >>> LINE(2, defObj=def1, color='#0000ff')
    LINE2:ds0a#0000ff
    >>> LINE(1, defObj=vdef1, color='#ff0000')
    LINE1:ds0max#ff0000
    >>> LINE(1, color='#ff0000')
    Traceback (most recent call last):
    Exception: You must provide either a value or a definition object.
    >>> LINE(1, value=vdef1, color='#ff0000')
    Traceback (most recent call last):
    ValueError: The parameter 'value' must be either a string or an integer.
    '''
    def __init__(self, width=None, value=None, defObj=None, color=None,
        legend='', stack=False):
        '''
        If a DEF, VDEF, or CDEF object as passed, the vname will
        be automatically extraced from the object and used.
        '''
        self.width = width
        self.color = color
        self.legend = legend
        self.stack = stack
        if value:
            if not (isinstance(value, str) or isinstance(value, int)):
                raise ValueError, "The parameter 'value' must be " + \
                    "either a string or an integer."
        else:
            if not defObj:
                raise Exception, "You must provide either a value " + \
                    "or a definition object."
            else:
                value = defObj.vname
        self.vname = value
        self.abbr = 'LINE'

    def __repr__(self):
        '''
        We override this method for preparing the class's data for
        use with RRDTool.
        '''
        main = self.abbr
        if self.width:
            main += str(self.width)
        main += ':%s' % self.vname
        if self.color:
            main += self.color
        if self.legend:
            main += ':"%s"' % self.legend
        if self.stack:
            main += ':STACK'
        return main
LINE = Line

class Area(Line):
    '''
    See LINE, however the area between the x-axis and the line will
    be filled.

    >>> def1 = DEF(rrdfile='/home/rrdtool/data/router1.rrd',
    ...   vname='ds0a', dsName='ds0')
    >>> vdef1 = VariableDefinition(vname='ds0max',
    ...   rpn='%s,MAXIMUM' % def1.dsName)

    # Now let's do some areas...
    >>> Area(value='ds0a', color='#cccccc', legend='Raw Router Data')
    AREA:ds0a#cccccc:"Raw Router Data"
    >>> AREA(defObj=vdef1, color='#cccccc', legend='Max Router Data',
    ...   stack=True)
    AREA:ds0max#cccccc:"Max Router Data":STACK
    '''
    def __init__(self, width=None, value=None, defObj=None, color=None,
        legend='', stack=False):
        '''
        If a DEF, VDEF, or CDEF object as passed, the vname will
        be automatically extraced from the object and used.
        '''
        super(Area, self).__init__(value=value, defObj=defObj,
            color=color, legend=legend, stack=stack)
        self.abbr = 'AREA'

AREA = Area

class GraphTick(object):
    '''
    Plot a tick mark (a vertical line) for each value of vname that
    is non-zero and not *UNKNOWN*. The fraction argument specifies
    the length of the tick mark as a fraction of the y-axis; the
    default value is 0.1 (10% of the axis). Note that the color
    specification is not optional.
    '''
    # XXX TODO
TICK = GraphTick

class GraphShift(object):
    '''
    Using this command RRDtool will graph the following elements
    with the specified offset. For instance, you can specify an
    offset of ( 7*24*60*60 = ) 604'800 seconds to ``look back'' one
    week. Make sure to tell the viewer of your graph you did this
    ... As with the other graphing elements, you can specify a
    number or a variable here.
    '''
    # XXX TODO
SHIFT = GraphShift

class GraphXGrid(object):
    '''
    The x-axis label is quite complex to configure. If you don't
    have very special needs it is probably best to rely on the
    autoconfiguration to get this right. You can specify the string
    none to suppress the grid and labels altogether.

    The grid is defined by specifying a certain amount of time in
    the ?TM positions. You can choose from SECOND, MINUTE, HOUR,
    DAY, WEEK, MONTH or YEAR. Then you define how many of these
    should pass between each line or label. This pair (?TM:?ST)
    needs to be specified for the base grid (G??), the major grid
    (M??) and the labels (L??). For the labels you also must define
    a precision in LPR and a strftime format string in LFM. LPR
    defines where each label will be placed. If it is zero, the
    label will be placed right under the corresponding line (useful
    for hours, dates etcetera). If you specify a number of seconds
    here the label is centered on this interval (useful for Monday,
    January etcetera).

        --x-grid MINUTE:10:HOUR:1:HOUR:4:0:%X

    This places grid lines every 10 minutes, major grid lines every
    hour, and labels every 4 hours. The labels are placed under the
    major grid lines as they specify exactly that time.

        --x-grid HOUR:8:DAY:1:DAY:1:0:%A

    This places grid lines every 8 hours, major grid lines and
    labels each day. The labels are placed exactly between two major
    grid lines as they specify the complete day and not just midnight.
    '''

class GraphYGrid(object):
    '''
    Y-axis grid lines appear at each grid step interval. Labels are
    placed every label factor lines. You can specify -y none to
    suppress the grid and labels altogether. The default for this
    option is to automatically select sensible values.
    '''

class ColorAttributes(object):
    '''
    This class is repr'ed without a leading '--color' because that
    will be provided by the graph class when it's color attribute
    is set to an instance of this class.

    >>> ColorAttributes(background='#000000', axis='#FFFFFF')
    AXIS#FFFFFF --color BACK#000000
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
    >>> ca
    ARROW#FFFFFF --color AXIS#FFFFFF --color BACK#333333 --color CANVAS#333333 --color FONT#FFFFFF --color FRAME#AAAAAA --color MGRID#CCCCCC --color SHADEA#000000 --color SHADEB#111111
    '''
    def __init__(self, background=None, canvas=None,
        lefttop_border=None, rightbottom_border=None, major_grid=None,
        font=None, axis=None, frame=None, arrow=None):
        '''
        Each of the parameters that gets pass when initializing
        this class take only a hexidecimal color as a value.
        '''
        self.back = background
        self.canvas = canvas
        self.shadea = lefttop_border
        self.shadeb = rightbottom_border
        self.mgrid = major_grid
        self.font = font
        self.axis = axis
        self.frame = frame
        self.arror = arrow

    def __repr__(self):
        joiner = ' --color '
        params = self.__dict__.items()
        params.sort()
        attrs = [ name.upper()+color for name,color in params if color ]
        return joiner.join(attrs)

class Graph(object):
    '''
    rrdtool graph needs data to work with, so you must use one or
    more data definition statements to collect this data. You are
    not limited to one database, it's perfectly legal to collect
    data from two or more databases (one per statement, though).

    If you want to display averages, maxima, percentiles, etcetera
    it is best to collect them now using the variable definition
    statement. Currently this makes no difference, but in a future
    version of rrdtool you may want to collect these values before
    consolidation.

    The data fetched from the RRA is then consolidated so that there
    is exactly one datapoint per pixel in the graph. If you do not
    take care yourself, RRDtool will expand the range slightly if
    necessary. Note, in that case the first and/or last pixel may
    very well become unknown!

    Sometimes data is not exactly in the format you would like to
    display it. For instance, you might be collecting bytes per
    second, but want to display bits per second. This is what the
    data calculation command is designed for. After consolidating
    the data, a copy is made and this copy is modified using a
    rather powerful RPN command set.

    When you are done fetching and processing the data, it is time
    to graph it (or print it). This ends the rrdtool graph sequence.

    # Let's create and RRD file and dump some data in it
    >>> import tempfile
    >>> from rrd import RRD, RRA, DS
    >>> dss = []
    >>> rras = []
    >>> tfile = tempfile.NamedTemporaryFile()
    >>> filename = tfile.name
    >>> ds1 = DS(dsName='speed', dsType='COUNTER', heartbeat=600)
    >>> dss.append(ds1)
    >>> rra1 = RRA(cf='AVERAGE', xff=0.5, steps=1, rows=24)
    >>> rra2 = RRA(cf='AVERAGE', xff=0.5, steps=6, rows=10)
    >>> rras.extend([rra1, rra2])
    >>> my_rrd = RRD(filename, ds=dss, rra=rras, start=920804400)
    >>> my_rrd.create()
    >>> import os
    >>> os.path.exists(filename)
    True
    >>> my_rrd.bufferValue('920805600', '12363')
    >>> my_rrd.bufferValue('920805900', '12363')
    >>> my_rrd.bufferValue('920806200', '12373')
    >>> my_rrd.bufferValue('920806500', '12383')
    >>> my_rrd.update()
    >>> my_rrd.bufferValue('920806800', '12393')
    >>> my_rrd.bufferValue('920807100', '12399')
    >>> my_rrd.bufferValue('920807400', '12405')
    >>> my_rrd.bufferValue('920807700', '12411')
    >>> my_rrd.bufferValue('920808000', '12415')
    >>> my_rrd.bufferValue('920808300', '12420')
    >>> my_rrd.bufferValue('920808600', '12422')
    >>> my_rrd.bufferValue('920808900', '12423')
    >>> my_rrd.update()

    # Let's set up the objects that will be added to the graph
    >>> def1 = DEF(rrdfile=my_rrd.filename, vname='myspeed', dsName=ds1.name)
    >>> cdef1 = CDEF(vname='kmh', rpn='%s,3600,*' % def1.vname)
    >>> cdef2 = CDEF(vname='fast', rpn='kmh,100,GT,kmh,0,IF')
    >>> cdef3 = CDEF(vname='good', rpn='kmh,100,GT,0,kmh,IF')
    >>> vdef1 = VDEF(vname='mymax', rpn='%s,MAXIMUM' % def1.vname)
    >>> vdef2 = VDEF(vname='myavg', rpn='%s,AVERAGE' % def1.vname)
    >>> line1 = LINE(value=100, color='#990000', legend='Maximum Allowed')
    >>> area1 = AREA(defObj=cdef3, color='#006600', legend='Good Speed')
    >>> area2 = AREA(defObj=cdef2, color='#CC6633', legend='Too Fast')
    >>> line2 = LINE(defObj=vdef2, color='#000099', legend='My Average', stack=True)
    >>> gprint1 = GPRINT(vdef2, '%6.2lf kph')

    # Let's configure some custom colors for the graph
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

    # Now that we've got everything set up, let's make a graph
    >>> graphfile = tempfile.NamedTemporaryFile()
    >>> g = Graph(graphfile.name, start=920805000, end=920810000,
    ...   vertical_label='km/h', color=ca, imgformat='png')
    >>> g.data.extend([def1, cdef1, cdef2, cdef3, vdef1, vdef2, line1,
    ...   area1, area2, line2, gprint1])
    >>> g.write()
    >>> os.path.exists(graphfile.name)
    True
    '''
    # Note that we don't use the Twisted camel case convention for the
    # parameters in the following method signature due to the fact that these
    # are what is used by RRDTool. Stuff will break if we don't.
    def __init__(self, filename, start=None, end=None, step=None,
        title='', vertical_label='', width=None, height=None,
        only_graph=None, upper_limit=None, lower_limit=None,
        rigid=False, alt_autoscale=None, alt_autoscale_max=None,
        no_gridfit=False, x_grid=None, y_grid=None,
        alt_y_grid=False, logarithmic=False, units_exponent=None,
        units_length=None, lazy=False, imginfo=None, color=None,
        zoom=None, font=None, font_render_mode=None,
        font_smoothing_threshold=None, slope_mode=None,
        imgformat='', interlaced=False, no_legend=False,
        force_rules_legend=False, tabwidth=None, base=None, backend=external):

        self.filename = filename
        if not imgformat:
            fn, ext = filename.split(os.extsep)
            imgformat = ext
        self.imgformat = validateImageFormat(imgformat)

        self.start = start
        self.end = end
        self.step = step
        self.title = title
        self.vertical_label = vertical_label
        self.width = width
        self.height = height
        self.only_graph = only_graph
        self.upper_limit = upper_limit
        self.lower_limit = lower_limit
        self.rigid = rigid
        self.alt_autoscale = alt_autoscale
        self.alt_autoscale_max = alt_autoscale_max
        self.no_gridfit = no_gridfit
        self.x_grid = x_grid
        self.y_grid = y_grid
        self.alt_y_grid = alt_y_grid
        self.logarithmic = logarithmic
        self.units_exponent = units_exponent
        self.color = color
        self.zoom = zoom
        self.font = font
        self.font_render_mode = font_render_mode
        self.interlaced = interlaced
        self.no_legend = no_legend
        self.force_rules_legend = force_rules_legend
        self.tabwidth = tabwidth
        self.base = base
        self.backend = backend

        if filename.strip() == '-':
            # send to stdout
            pass
        self.data = []

    def write(self, debug=False):
        '''
        '''
        data = self.backend.prepareObject('graph', self)
        if debug:
            print data
        self.backend.graph(*data)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
