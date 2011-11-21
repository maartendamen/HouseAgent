import os

def get_configurationpath():
    '''
    This function get's the path for the configuration files. 
    On Windows this should return a 'programdata' path. 
    Linux and OSX default to the current working directory of the plug-in.
    If the expected path doesn't exist, we assume we are running a development
    environment and return the current working directory.
    @return: config_path, current configuration path for plug-in.
    '''
    if os.name == 'nt':
        from win32com.shell import shellcon, shell            
        config_path = os.path.join(shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0), 'HouseAgent')
    else:
        config_path = os.path.join('/', 'etc', 'HouseAgent')
        
    # If the path doesn't exist, lets assume we are running in a dev environment
    # and just return the current working directory.
    
    if not os.path.exists(config_path):
        config_path = os.getcwd()
        
    return config_path

def get_pluginpath():
    '''
    This function get's the path for the plugin files. 
    On Windows this should return a 'programdata' path. 
    Linux and OSX default to the current working directory of the plug-in.
    If the expected path doesn't exist, we assume we are running a development
    environment and return the current working directory.
    @return: config_path, current configuration path for plug-in.
    '''
    if os.name == 'nt':
        from win32com.shell import shellcon, shell            
        config_path = os.path.join(shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0), 'HouseAgent')
    else:
        config_path = os.path.join('/', 'usr', 'share', 'HouseAgent')
        
    # If the path doesn't exist, lets assume we are running in a dev environment
    # and just return the current working directory.
    
    if not os.path.exists(config_path):
        config_path = os.getcwd()
        
    return config_path