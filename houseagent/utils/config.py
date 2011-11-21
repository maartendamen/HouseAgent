import error
import ConfigParser
import os
import sys

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
        self.embedded = _ConfigEmbedded(parser)

class _ConfigGeneral:

    def __init__(self, parser):
        if os.name == 'nt':
            from win32com.shell import shellcon, shell
            programdata = os.path.join(shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0), 'HouseAgent')      
        
        self.logpath = _getOpt(
                parser.get, "general", "logpath", None)

        if self.logpath != None and self.logpath != "":
            self.logpath = self.logpath
        else:
            if os.name == 'nt':
                if hasattr(sys, 'frozen'):
                    # Special case for binary Windows version
                    self.logpath = os.path.join(programdata, 'logs')
                elif os.path.exists(os.path.join(programdata, 'logs')):
                    self.logpath = os.path.join(programdata, 'logs')
                elif os.path.exists(os.path.join(os.getcwd(), 'logs')):
                    # development
                    self.logpath = os.path.join(os.getcwd(), 'logs')
            else:
                logpath = os.path.join(os.sep, 'var', 'log', 'HouseAgent')
                
                if os.path.exists(logpath):
                    self.logpath = logpath
                elif os.path.exists(os.path.join(os.getcwd(), 'logs')):
                    self.logpath = os.path.join(os.getcwd(), 'logs')        
        
        self.loglevel = _getOpt(
                parser.get, "general", "loglevel", "debug")
        self.runasservice = _getOpt(
                                    parser.getboolean, "general", "runasservice", False)
        
        dbpath = _getOpt(parser.get, "general", "dbpath", None)
        if dbpath != None and dbpath != "":
            self.dbfile = os.path.join(dbpath, 'houseagent.db')
        else:
            if os.name == 'nt':
                if hasattr(sys, 'frozen'):
                    # Special case for binary Windows version
                    self.dbfile = os.path.join(programdata, 'houseagent.db')
                elif os.path.exists(os.path.join(programdata, 'houseagent.db')):
                    self.dbfile = os.path.join(programdata, 'houseagent.db')
                elif os.path.exists(os.path.join(os.getcwd(), 'houseagent.db')):
                    # development
                    self.dbfile = os.path.join(os.getcwd(), 'houseagent.db')
            else:
                dbfile = os.path.join(os.sep, 'etc', 'houseagent.db')
                
                if os.path.exists(dbfile):
                    self.dbfile = dbfile
                elif os.path.exists(os.path.join(os.getcwd(), 'houseagent.db')):
                    self.dbfile = os.path.join(os.getcwd(), 'houseagent.db')

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
        
class _ConfigEmbedded:
    
    def __init__(self, parser):
        self.enabled = _getOpt(
                parser.getboolean, "embedded", "enabled", False)
        self.db_save_interval = _getOpt(
                parser.getint, "embedded", "dbsaveinterval", 0)