import sys

class Error(Exception):
    """
    Base class for errors
    """
    def __str__(self):
        return repr(self)


class ConfigError(Error):
    """
    Error in config file
    """
    def __init__(self, identifier):
        Error.__init__(self)
        self.identifier = identifier

    def __repr__(self):
        return("<ConfigError for parameter \"%s\" (wrong or undefined)>"\
                % (self.identifier))

class ConfigFileNotFound(Error):
    '''
    Configuration file not found error message.
    '''
    def __init__(self, identifier):
        Error.__init__(self)
        self.identifier = identifier

    def __repr__(self):
        return("<Configuration file not found in any of the following known locations: \"%s\">"\
                % (self.identifier))   