from houseagent.core.database import Database
from houseagent.core.web_pages import *
from twisted.internet import reactor
from twisted.web.server import Site
from twisted.web.static import File
import os.path
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

    def load_pages(self, root):
        '''
        This function dynamically loads pages from plugins.
        A pages.py file with atleast the init_pages() function must exist in the 
        plugins/<pluginname>/ folder.
        @return: an array of loaded modules
        '''
        plugin_dir = os.path.join(os.path.dirname(houseagent.__file__), "plugins")
        plugin_dirs = os.listdir(plugin_dir)
        
        for dir in plugin_dirs:
            if os.path.isdir(os.path.join(plugin_dir, dir)):
                print "Plugin directory found, directory: %s" % dir
                try:
                    file, pathname, description = imp.find_module("pages", [os.path.join(plugin_dir, dir)])                
                    mod = imp.load_module("pages", file, pathname, description)
                    mod.init_pages(root, self.coordinator, self.db)
                    print "Loaded pages for plugin %s" % dir
                except:
                    print "Warning cannot load pages module for %s, no pages.py file?" % dir
        
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
        root.putChild("event_workflow", Event_workflow())
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
        root.putChild("control_dimmer", Control_dimmer(self.coordinator))
        root.putChild("control_stat", Control_stat(self.coordinator))

        # Load plugin pages
        self.load_pages(root)
        
        reactor.listenTCP(self.port, site)