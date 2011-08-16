import os

def get_configurationpath():
    '''
    This function get's the path for the configuration files. On Windows this should return a 
    'programdata' path. 
    Linux and OSX default to the current working directory of the plug-in.
    @return: config_path, current configuration path for plug-in.
    '''
    try:
        from win32com.shell import shellcon, shell            
        config_path = os.path.join(shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0), 'HouseAgent')
    except ImportError:
        config_path = os.path.join('/','etc', 'HouseAgent')
    
    return config_path