import error
import ConfigParser

def _getOpt(get, section, option, default = None):
    res = default
    try:
        res = get(section, option)
    except ConfigParser.NoOptionError:
        if res == None:
            raise error.ConfigError, ("[%s]::%s" % (section,option))

    return res


def _getListOpt(get, section, option, separator, default = None,
        allowEmpty = False):
    value = _getOpt(get, section, option, default)

    res = []
    for x in value.split(separator):
        x = x.strip()
        if not allowEmpty and not x:
            continue
        res.append(x)

    return res


class Config:

    def __init__(self, config_file="HouseAgent.conf"):

        self.file_path = config_file
        # open parser, load config file
        parser = ConfigParser.ConfigParser()
        f = open(self.file_path, 'r')
        parser.readfp(f)
        f.close()

        # load config
        self.general = _ConfigGeneral(parser)
        self.webserver = _ConfigWebserver(parser)
        self.zmq = _ConfigZMQ(parser)


class _ConfigGeneral:

    def __init__(self, parser):
        self.logpath = _getOpt(
                parser.get, "general", "logpath", None)
        self.loglevel = _getOpt(
                parser.get, "general", "loglevel", "debug")
        self.runasservice = _getOpt(
                                    parser.getboolean, "general", "runasservice", False)


class _ConfigWebserver:

    def __init__(self, parser):
        self.port = _getOpt(
                parser.getint, "webserver", "port", 8080)


class _ConfigZMQ:

    def __init__(self, parser):
        self.broker_host = _getOpt(
                parser.get, "zmq", "host", "*")
        self.broker_port = _getOpt(
                parser.getint, "zmq", "port", 13001)

