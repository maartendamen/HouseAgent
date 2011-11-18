import sys
import os
from houseagent.utils.error import ConfigFileNotFound

"""
This init file defines some commonly used HouseAgent paths.
These paths depend on the operating system version/type, and the working situation (development/test and production) 
"""

def config_file():
    '''
    This function determines the location of the HouseAgent configuration file. 
    For Windows the following locations are checked: ProgramData\\HouseAgent and the current working directory.
    In case of an other OS the following locations are checked: /etc followed by the current working directory.
    '''
    
    # Windows
    if os.name == 'nt':
    
        from win32com.shell import shellcon, shell   
        config_file = config_file = os.path.join(shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0), 'HouseAgent', 'HouseAgent.conf')
        
        if hasattr(sys, 'frozen'):
            # Special case for binary Windows version
            return config_file
        elif os.path.exists(config_file):
            return config_file
        elif os.path.exists(os.path.join(os.getcwd(), 'HouseAgent.conf')):
            # development
            return os.path.join(os.getcwd(), 'HouseAgent.conf')
        else:
            raise ConfigFileNotFound("ProgramData or working directory.")

    # OSX and Linux    
    else:
        config_file = os.path.join(os.sep, 'etc', 'HouseAgent.conf')
        
        if os.path.exists(config_file):
            return config_file
        elif os.path.exists(os.path.join(os.getcwd(), 'HouseAgent.conf')):
            return os.path.join(os.getcwd(), 'HouseAgent.conf')
        else:
            raise ConfigFileNotFound("/etc/ or working directory.")

config_file = config_file()
 
""" Template directory """
if hasattr(sys, 'frozen'):
    template_dir = os.path.join(os.path.dirname(sys.executable), 'templates')
else:
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')

""" Template plugin directory """
if hasattr(sys, 'frozen'):
    template_plugin_dir = os.path.join(os.path.dirname(sys.executable), 'plugins')
else:
    template_plugin_dir = os.path.join(os.path.dirname(__file__), 'plugins')
