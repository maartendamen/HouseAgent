from houseagent.core.database import Database
from houseagent.core.web_pages import *
from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.web.static import File
import os.path
import sys
import re
import imp

class Web(object):
    '''
    This is the HouseAgent main web interface.
    '''
    def __init__(self, port, coordinator, eventengine):
        self.port = port # web server 0listening port
        self.coordinator = coordinator
        self.eventengine = eventengine
        self.db = Database() 

    def load_pages(self, path):
            
        files = os.listdir( os.path.join (os.path.dirname(houseagent.__file__), path) )
        test = re.compile(".py$", re.IGNORECASE)          
        files = filter(test.search, files)                     
        filenameToModuleName = lambda f: os.path.splitext(f)[0]
        moduleNames = sorted(map(filenameToModuleName, files))
        print sys.path
        print moduleNames
        f, filename, desc = imp.find_module('houseagent')
        ha = imp.load_module('houseagent', f, filename, desc)
        f, filename, desc = imp.find_module('pages', ha.__path__)
        plugin = imp.load_module('pages', f, filename, desc)
        modules = []
        
        #print moduleNames
        for m in moduleNames:
            # skip any files starting with '__', such as __init__.py
            if m.startswith('__'):
                continue
            try:
                f, filename, desc = imp.find_module(m, plugin.__path__)
                modules.append( imp.load_module(m, f, filename, desc))
            except ImportError:
                continue
        
        return modules
        
    def start(self):
        '''
        Starts the HouseAgent web interface.
        '''
        root = Resource()
        site = Site(root)
        
        # Main page
        root.putChild("", Root())
        
        # Room management
        root.putChild("location_add", Location_add())
        root.putChild("location_added", Location_added())
        root.putChild("locations", Locations())
        root.putChild("location_del", Location_del())
        root.putChild("location_edit", Location_edit())
        root.putChild("location_edited", Location_edited())
        
        # Plugin management
        root.putChild("plugin_add", Plugin_add())
        root.putChild("plugin_add_do", Plugin_add_do(self.coordinator))
        root.putChild("plugin_status", Plugin_status(self.coordinator))
        root.putChild("plugins", Plugins())
        root.putChild("plugin_del", Plugin_del())
        root.putChild("plugin_edit", Plugin_edit())
        root.putChild("plugin_edited", Plugin_edited())
        
        # Device management
        root.putChild("device_add", Device_add())
        root.putChild("device_save", Device_save())
        root.putChild("device_list", Device_list())
        root.putChild("device_man", Device_management())
        root.putChild("device_del", Device_del())
        root.putChild("device_edit", Device_edit())
        root.putChild("history", History())
        root.putChild("control_type", Control_type())

        # Events
        root.putChild("event_create", Event_create())
        root.putChild("event_value_by_id", Event_value_by_id())
        root.putChild("event_getvalue", Event_getvalue())
        root.putChild("event_save", Event_save(self.eventengine))
        root.putChild("event_control_values_by_id", Event_control_values_by_id())
        root.putChild("event_control_types_by_id", Event_control_types_by_id())
        root.putChild("events", Events())
        root.putChild("event_del", Event_del(self.eventengine))

        root.putChild("css", File(os.path.join(houseagent.template_dir, 'css')))
        root.putChild("js", File(os.path.join(houseagent.template_dir, 'js')))
        root.putChild("images", File(os.path.join(houseagent.template_dir, 'images')))
                
        root.putChild("test", Test())
        root.putChild("graphdata", GraphData())
        root.putChild("create_graph", CreateGraph())
        
        root.putChild("control", Control())        
        root.putChild("control_onoff", Control_onoff(self.coordinator))
        root.putChild("control_stat", Control_stat(self.coordinator))
        
        # Load plugin related web pages
        modules = self.load_pages("pages")
        for module in modules:
            module.init_pages(root, self.coordinator, self.db)

        reactor.listenTCP(self.port, site)
