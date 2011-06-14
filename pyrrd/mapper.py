from pyrrd.node import RRDXMLNode


class DSMixin(object):

    def __init__(self):
        self.ds = []


class Mapper(object):
    """
    """
    __slots__ = []
    __skip_repr__ = []

    def setAttributes(self, attributes):
        for name, value in attributes.items():
            if name not in self.__skip_repr__:
                setattr(self, name, value)

    def getData(self):
        items = {}
        for name in self.__slots__:
            if name not in self.__skip_repr__:
                items[name] = getattr(self, name, None)
        return items

    def map(self, node):
        """
        """
        self.setAttributes(node.attributes)

    def printInfo(self):
        for name, value in self.getData().items():
            if value is None:
                continue
            print "%s = %s" % (name, str(value))


class RowMapper(Mapper):
    """
    """
    __slots__ = ["v"]


class DatabaseMapper(Mapper):
    """
    """
    __slots__ = ["rows"]
    __skip_repr__ = ["rows"]

    def __init__(self):
        self.rows = []


class CDPrepDSMapper(Mapper):
    """
    """
    __slots__ = [
        "primary_value",
        "secondary_value",
        "value",
        "unknown_datapoints",
        ]

    def printInfo(self, prefix, index):
        for name, value in self.getData().items():
            if value is None:
                continue
            print "%s.cdp_prep[%s].%s = %s" % (prefix, index, name, str(value))


class CDPPrepMapper(Mapper, DSMixin):
    """
    """
    __slots__ = ["ds"]
    __skip_repr__ = ["ds"]


class RRAMapper(Mapper, DSMixin):
    """
    """
    __slots__ = [
        "cf",
        "pdp_per_row",
        "xff",
        "cdp_prep",
        "ds",
        "steps",
        "rows",
        "alpha",
        "beta",
        "seasonal_period",
        "rra_num",
        "gamma",
        "threshold",
        "window_length",
        "database",
        ]
    __skip_repr__ = ["ds"]

    def map(self, node):
        super(RRAMapper, self).map(node)
        for subNode in node.cdp_prep.ds:
            ds = CDPrepDSMapper()
            ds.map(subNode)
            self.ds.append(ds)

    def getData(self):
        data = super(RRAMapper, self).getData()
        data["ds"] = [ds.getData() for ds in self.ds]
        return data

    def printInfo(self, index):
        prefix = "rra[%s]" % index
        for name, value in self.getData().items():
            if value is None:
                continue
            print "%s.%s = %s" % (prefix, name, str(value))
        for index, ds in enumerate(self.ds):
            ds.printInfo(prefix, index)


class DSMapper(Mapper):
    """
    """
    __slots__ = [
        "name",
        "type",
        "minimal_heartbeat",
        "min",
        "max",
        "last_ds",
        "value",
        "unknown_sec",
        "rpn",
        ]

    def printInfo(self):
        for name, value in self.getData().items():
            if value is None:
                continue
            if name != self.name:
                print "ds[%s].%s = %s" % (self.name, name, str(value))


class RRDMapper(Mapper, DSMixin):
    """
    """
    __slots__ = [
        "version",
        "step",
        "lastupdate",
        "ds",
        "rra",
        "values",
        "start",
        "mode",
        "filename",
        ]
    __skip_repr__ = ["ds", "rra", "mode"]

    def __init__(self):
        self.mode = None
        super(RRDMapper, self).__init__()
        self.rra = []

    def getData(self):
        """
        """
        if not (self.ds or self.rra):
            self.map()
        data = super(RRDMapper, self).getData()
        data["ds"] = [ds.getData() for ds in self.ds]
        data["rra"] = [rra.getData() for rra in self.rra]
        return data

    def printInfo(self):
        super(RRDMapper, self).printInfo()
        for ds in self.ds:
            ds.printInfo()
        for index, rra in enumerate(self.rra):
            rra.printInfo(index)

    def map(self):
        """
        The map method does several things:
            1) if the RRD object (instantiated from this class or a subclass)
               is in "write" mode, there is no need to parse the XML and map
               it; there is already an object representation. In this case, the
               majority of this method is skipped.
            2) if the RRD object is in "read" mode, it needs to pull data out
               of the rrd file; it does this by loading (which dumps to XML and
               then reads in the XML).
            3) once the XML has been parsed, it maps the XML to objects.
        """
        if self.mode == "w":
            return
        # The backend is defined by the subclass of this class, as is the
        # filename.
        tree = self.backend.load(self.filename)
        node = RRDXMLNode(tree)
        super(RRDMapper, self).map(node)
        for subNode in node.ds:
            ds = DSMapper()
            ds.map(subNode)
            self.ds.append(ds)
        for subNode in node.rra:
            rra = RRAMapper()
            rra.map(subNode)
            self.rra.append(rra)
