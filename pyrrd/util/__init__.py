from time import mktime
from datetime import datetime

try:
    from xml.etree import ElementTree
except ImportError:
    from elementtree import ElementTree


XML = ElementTree.XML


def epoch(dt_obj=None):
    '''
    >>> dt = datetime(1972, 8, 17)
    >>> epoch(dt)
    82879200
    >>> now = epoch()
    >>> type(now)
    <type 'int'>
    '''
    if not dt_obj:
        dt_obj = datetime.now()
    return int(mktime(dt_obj.timetuple()))


class Attributes(object):
    """
    A simple object for storing attributes.
    """


class NaN(float):

    def __repr__(self):
        return "nan"

    __str__ = __repr__
