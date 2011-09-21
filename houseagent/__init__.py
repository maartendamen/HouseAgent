import sys
import os

"""
This init file defines some commonly used HouseAgent paths.
These paths depend on the operating system version/type, and the working situation (development/test and production) 
"""

""" Database name and location """
db_name = 'houseagent.db'

if os.name == 'nt':
    # Windows specific code
    from win32com.shell import shellcon, shell            
    db_path = os.path.join(shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0), 'HouseAgent', db_name)  
else:    
    db_path = os.path.join(sys.prefix, 'share', 'HouseAgent', db_name)
    
if os.path.exists(db_path):
    # Production environment
    db_location = db_path
else:
    # Most likely test/development environment
    db_location = db_name

""" Template directory """
template_dir = os.path.join(os.path.dirname(__file__), 'templates')

""" Template plugin directory """
template_plugin_dir = os.path.join(os.path.dirname(__file__), 'plugins')

""" Logging directory """
if os.name == 'nt':
    from win32com.shell import shellcon, shell            
    log_path = os.path.join(shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0), 'HouseAgent', 'logs')  
else:    
    log_path = os.path.join(sys.prefix, 'share', 'HouseAgent', 'logs')
    
if os.path.exists(log_path):
    log_path = log_path
else:
    try:
        os.mkdir(log_path)
    except:
        print "Error creating log directory!"
        log_path = log_path