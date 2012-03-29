import sys
import houseagent
import datetime
import json
import os.path
import imp
from twisted.internet import reactor
from twisted.web.server import Site
from twisted.web.static import File
from pyrrd.rrd import RRD
from mako.lookup import TemplateLookup
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.error import CannotListenError
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from twisted.web.error import NoResource
from uuid import uuid4
from twisted.web import http
            
class Web(object):
    '''
    This class provides the core web interface for HouseAgent.
    All management functions to control HouseAgent take place from here.
    '''
    
    def __init__(self, log, host, port, backlog, coordinator, eventengine, database):
        '''
        Initialize the web interface.
        @param port: the port on which the web server should listen
        @param coordinator: an instance of the network coordinator in order to interact with it
        @param eventengine: an instance of the event engine in order to interact with it
        @param database: an instance of the database layer in order to interact with it
        '''
        self.host = host # web server interface
        self.port = port # web server listening port
        self.backlog = backlog # size of the listen queue
        self.coordinator = coordinator
        self.eventengine = eventengine
        self.db = database
        
        self.log = log

        root = Resource()
        site = Site(root)
        
        # Main page
        root.putChild("", Root())
        
        # Location management
        root.putChild('locations', Locations(self.db))
        root.putChild('locations_view', Locations_view())
        
        # Plugin management
        root.putChild('plugins', Plugins(self.db, self.coordinator))
        root.putChild('plugins_view', Plugins_view())
        
        # Device management
        root.putChild('devices', Devices(self.db))
        root.putChild('devices_view', Devices_view())
        
        # Value management
        root.putChild('values', Values(self.db, self.coordinator))
        root.putChild('values_view', Values_view())
        root.putChild('history_types', HistoryTypes(self.db)) 
        root.putChild('history_periods', HistoryPeriods(self.db))
        root.putChild('control_types', ControlTypes(self.db))
        
        root.putChild("device_add", Device_add(self.db))
        root.putChild("device_save", Device_save(self.db))
        root.putChild("device_list", Device_list(self.db))
        root.putChild("device_man", Device_management(self.db))
        root.putChild("device_del", Device_del(self.db))
        root.putChild("device_edit", Device_edit(self.db))
        root.putChild("history", History(self.db))

        # Events
        root.putChild("event_create", Event_create(self.db))
        root.putChild("event_value_by_id", Event_value_by_id(self.db))
        root.putChild("event_getvalue", Event_getvalue(self.db))
        root.putChild("event_save", Event_save(self.eventengine, self.db))
        root.putChild("event_control_values_by_id", Event_control_values_by_id(self.db))
        root.putChild("event_control_types_by_id", Event_control_types_by_id(self.db))
        root.putChild("events", Events(self.db))
        root.putChild("event_del", Event_del(self.eventengine, self.db))

        root.putChild("css", File(os.path.join(houseagent.template_dir, 'css')))
        root.putChild("js", File(os.path.join(houseagent.template_dir, 'js')))
        root.putChild("images", File(os.path.join(houseagent.template_dir, 'images')))


        root.putChild("graphdata", GraphData())
        root.putChild("create_graph", CreateGraph(self.db))
        
        root.putChild("control", Control(self.db))        
        root.putChild("control_onoff", Control_onoff(self.coordinator))
        root.putChild("control_dimmer", Control_dimmer(self.coordinator))
        root.putChild("control_stat", Control_stat(self.coordinator))

        # Load plugin pages
        self.load_pages(root)
        
        try:
            reactor.listenTCP(self.port, site, self.backlog, self.host)
        except CannotListenError,e:
            log.critical("--> %s" % e)
            sys.exit(1)

    def load_pages(self, root):
        '''
        This function dynamically loads pages from plugins.
        A pages.py file with atleast the init_pages() function must exist in the 
        plugins/<pluginname>/ folder.
        @return: an array of loaded modules
        '''
        if hasattr(sys, 'frozen'):
            plugin_dir = os.path.join(os.path.dirname(sys.executable), "plugins")
        else:
            plugin_dir = os.path.join(os.path.dirname(houseagent.__file__), "plugins")
        plugin_dirs = os.listdir(plugin_dir)
        
        for dir in plugin_dirs:
            if os.path.isdir(os.path.join(plugin_dir, dir)):
                self.log.debug("--> Plugin directory found, directory: %s" % dir)
                try:
                    file, pathname, description = imp.find_module("pages", [os.path.join(plugin_dir, dir)])                
                    mod = imp.load_module("pages", file, pathname, description)
                    mod.init_pages(root, self.coordinator, self.db)
                    self.log.debug("--> Loaded pages for plugin %s" % dir)
                except ImportError:
                    self.log.warning("--> Warning cannot load pages module for %s, no pages.py file?" % dir)

class Root(Resource):
    '''
    This is the main page for HouseAgent.
    '''
    def render_GET(self, request):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('index.html')
        return str(template.render())
    
class HouseAgentREST(Resource):
    '''
    This class implements a basic REST interface.
    '''
    def __init__(self, db):
        Resource.__init__(self)
        self.db = db
        self._load()
        self._objects = []
    
    # functions that must be implemented
    def _load(self):
        raise NotImplementedError
    
    def _add(self, **kwargs):
        raise NotImplementedError
    
    def _edit(self, **kwargs):
        raise NotImplementedError
        
    # internal functions
    def render_GET(self, request):
        output = []
        for obj in self._objects:
            output.append(obj.json())

        return json.dumps(output)
    
    def _done(self):
        self.request.finish()
        
    def _reload(self):
        self._objects = []
        self._load()
    
    def render_POST(self, request):
        self.request = request
        self._add(request.args)
        return NOT_DONE_YET
    
    def render_PUT(self, request):
        self.request = request
        self._edit(http.parse_qs(request.content.read(), 1)) # http://twistedmatrix.com/pipermail/twisted-web/2007-March/003338.html
        return NOT_DONE_YET
           
    def getChild(self, name, request):
        for obj in self._objects:
            if name == str(obj.id):
                return obj
            
        return NoResource(message="The resource %s was not found" % request.URLPath())

class Location(Resource):
    '''
    This object represents a Location.
    '''
    def __init__(self, id, name, parent_name, parent):
        Resource.__init__(self)
        self.id = id
        self.name = name
        self.parent_name = parent_name
        self.parent = parent
        
    def json(self):
        return {'id': self.id, 'name': self.name, 'parent': self.parent_name}
    
    def render_GET(self, request):
        return json.dumps(self.json())
    
    def render_DELETE(self, request):
        self.request = request
        self.parent.delete(self)
        return NOT_DONE_YET

class Locations(HouseAgentREST):

    @inlineCallbacks            
    def _load(self):
        '''
        Load locations from the database.
        '''
        self._objects = []
        location_query = yield self.db.query_locations()
        
        for location in location_query:
            loc = Location(location[0], location[1], location[2], self)
            self._objects.append(loc)
    
    @inlineCallbacks
    def _add(self, parameters):
        try:
            parent = parameters['parent'][0]
        except KeyError:
            parent = None
        
        yield self.db.add_location(parameters['name'][0], parent)
        self._reload()
        self._done()
    
    @inlineCallbacks
    def _edit(self, parameters):
        try:
            parent = parameters['parent'][0]
            if parent == '':
                parent = None
        except KeyError:
            parent = None
        
        yield self.db.update_location(parameters['id'][0], parameters['name'][0], parent)
        self._reload()
        self._done()
    
    @inlineCallbacks
    def delete(self, obj):
        yield self.db.del_location(int(obj.id))
        self._objects.remove(obj)
        obj.request.finish()

class Locations_view(Resource):
    
    def render_GET(self, request):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('locations.html')
        return str(template.render())

class Plugin(Resource):
    '''
    This object represents a Plugin.
    '''
    def __init__(self, id, name, authcode, location, parent):
        Resource.__init__(self)
        self.id = id
        self.name = name
        self.authcode = authcode
        self.location = location
        self.parent = parent
        self.status = False
        
    def json(self):
        return {'id': self.id, 'name': self.name, 'authcode': self.authcode, 'location': self.location, 'status': self.status}
    
    def render_GET(self, request):
        return json.dumps(self.json())
    
    def render_DELETE(self, request):
        self.request = request
        self.parent.delete(self)
        return NOT_DONE_YET
    
class Plugins(HouseAgentREST):

    def __init__(self, db, coordinator):
        HouseAgentREST.__init__(self, db)
        self.coordinator = coordinator
        
    def render_GET(self, request):
        ''' 
        This gets overriden in order to support online/offline status
        '''
        output = []
        for obj in self._objects:
            for p in self.coordinator.plugins:
                if p.guid == obj.authcode:
                    obj.status = p.online            
            
            output.append(obj.json())

        return json.dumps(output)

    @inlineCallbacks            
    def _load(self):
        '''
        Load plugins from the database.
        '''
        self._objects = []
        plugin_query = yield self.db.query_plugins()
        
        for plugin in plugin_query:
            plug = Plugin(plugin[2], plugin[0], plugin[1], plugin[3], self)
            self._objects.append(plug)
    
    @inlineCallbacks
    def _add(self, parameters):
        try:
            location = parameters['location'][0]
        except KeyError:
            location = None
            
        uuid = uuid4()    
        yield self.db.register_plugin(parameters['name'][0], uuid, location)
        self._reload()
        self._done()
    
    @inlineCallbacks
    def _edit(self, parameters):
        try:
            location = parameters['location'][0]
        except KeyError:
            location = None
        
        yield self.db.update_plugin(parameters['id'][0], parameters['name'][0], location)
        self._reload()
        self._done()
    
    @inlineCallbacks
    def delete(self, obj):
        yield self.db.del_plugin(int(obj.id))
        self._objects.remove(obj)
        obj.request.finish()
        
class Plugins_view(Resource):
    
    def render_GET(self, request):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('plugins.html')
        return str(template.render())

class Device(Resource):
    '''
    This object represents a Device.
    '''
    def __init__(self, id, name, address, plugin, location, parent):
        Resource.__init__(self)
        self.id = id
        self.name = name
        self.address = address
        self.plugin = plugin
        self.location = location
        self.parent = parent
        
    def json(self):
        return {'id': self.id, 'name': self.name, 'address': self.address, 'plugin': self.plugin, 'location': self.location}
    
    def render_GET(self, request):
        return json.dumps(self.json())
    
    def render_DELETE(self, request):
        self.request = request
        self.parent.delete(self)
        return NOT_DONE_YET
    
class Devices(HouseAgentREST):

    @inlineCallbacks            
    def _load(self):
        '''
        Load plugins from the database.
        '''
        self._objects = []
        device_query = yield self.db.query_devices()
        
        for device in device_query:
            dev = Device(device[0], device[1], device[2], device[3], device[4], self)
            self._objects.append(dev)
    
    @inlineCallbacks
    def _add(self, parameters):  
        yield self.db.save_device(parameters['name'][0], parameters['address'][0], parameters['plugin'][0], parameters['location'][0])
        self._reload()
        self._done()
    
    @inlineCallbacks
    def _edit(self, parameters):       
        yield self.db.set_history(parameters['id'][0], parameters['history_period'][0], parameters['history_type'][0])
        yield self.db.set_controltype(parameters['id'][0], parameters['control_type'][0])
        self._reload()
        self._done()
    
    @inlineCallbacks
    def delete(self, obj):
        yield self.db.del_device(int(obj.id))
        self._objects.remove(obj)
        obj.request.finish()
        
class Devices_view(Resource):
    
    def render_GET(self, request):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('devices.html')
        return str(template.render())

class Value(Resource):
    '''
    This object represents a Value.
    '''
    def __init__(self, id, name, value, device, device_address, location, plugin, lastupdate, history_type, history_period, control_type, plugin_id):
        Resource.__init__(self)
        self.id = id
        self.name = name
        self.value = value
        self.device = device
        self.device_address = device_address
        self.location = location
        self.plugin = plugin
        self.lastupdate = lastupdate
        self.history_type = history_type
        self.history_period = history_period
        self.control_type = control_type
        self.plugin_id = plugin_id
        
    def json(self):
        return {'id': self.id, 'name': self.name, 'value': self.value, 'device': self.device, 'device_address': self.device_address,
                'location': self.location, 'plugin': self.plugin, 'lastupdate': self.lastupdate, 'history_type': self.history_type,
                'control_type': self.control_type, 'history_period': self.history_period, 'plugin_id': self.plugin_id}
    
    def render_GET(self, request):
        return json.dumps(self.json())
    
    def render_DELETE(self, request):
        self.request = request
        self.parent.delete(self)
        return NOT_DONE_YET
    
class Values(HouseAgentREST):

    def __init__(self, db, coordinator):
        HouseAgentREST.__init__(self, db)
        self.coordinator = coordinator

    def render_GET(self, request):
        self._objects = []
        self._load().addCallback(self.done)

        self.request = request

        return NOT_DONE_YET
    
    def done(self, result):
    
        output = []
        for obj in self._objects:
            output.append(obj.json())

        self.request.write(json.dumps(output))
        self.request.finish()
    
    @inlineCallbacks            
    def _load(self):
        '''
        Load plugins from the database.
        '''
        self._objects = []
        value_query = yield self.db.query_values()
        
        for value in value_query:
            val = Value(value[7], value[0], value[1], value[2], value[5], value[6], value[4], value[3], value[10], value[11], value[8], value[12])
            self._objects.append(val)
    
    @inlineCallbacks
    def _add(self, parameters):  
        yield self.db.save_device(parameters['name'][0], parameters['address'][0], parameters['plugin'][0], parameters['location'][0])
        self._reload()
        self._done()
    
    @inlineCallbacks
    def _edit(self, parameters):       
        yield self.db.save_device(parameters['name'][0], parameters['address'][0], parameters['plugin'][0], 
                                  parameters['location'][0], parameters['id'][0])
        self._reload()
        self._done()
    
    @inlineCallbacks
    def delete(self, obj):
        yield self.db.del_device(int(obj.id))
        self._objects.remove(obj)
        obj.request.finish()
    
    def getChild(self, name, request):
               
        try:
            action = request.args['action'][0]
        except KeyError:
            action = None
        
        if not action:
            for obj in self._objects:
                if name == str(obj.id):
                    return obj
                
            return NoResource(message="The resource %s was not found" % request.URLPath())
        else:
            for obj in self._objects: 
                if name == str(obj.id): 
                    device_address = obj.device_address 
                    plugin_id = obj.plugin_id
                    
                    def control_result(result):
                        request.write(str(result))
                        request.finish()
                    
                    if action == 'poweron':
                        print self.coordinator
                        self.coordinator.send_poweron(plugin_id, device_address).addCallback(control_result)
                    
                    return NOT_DONE_YET
        
class Values_view(Resource):
    
    def render_GET(self, request):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('values.html')
        return str(template.render())

class HistoryType(Resource):
    '''
    This object represents a HistoryType.
    '''
    def __init__(self, id, name):
        Resource.__init__(self)
        self.id = id
        self.name = name
        
    def json(self):
        return {'id': self.id, 'name': self.name}
    
    def render_GET(self, request):
        return json.dumps(self.json())

class HistoryTypes(HouseAgentREST):
    
    @inlineCallbacks            
    def _load(self):
        '''
        Load history types from the database.
        '''
        self._objects = []
        history_type_query = yield self.db.query_history_types()
        
        for history_type in history_type_query:
            hist = HistoryType(history_type[0], history_type[1])
            self._objects.append(hist)    

class HistoryPeriod(Resource):
    '''
    This object represents a HistoryPeriod.
    '''
    def __init__(self, id, name, secs, sysflag):
        Resource.__init__(self)
        self.id = id
        self.name = name
        self.secs = secs
        self.sysflag = sysflag

    def json(self):
        return {"id": self.id, "name": self.name,
                "secs": self.secs, "sysflag": self.sysflag}

    def render_GET(self, request):
        return json.dumps(self.json())

class HistoryPeriods(HouseAgentREST):

    @inlineCallbacks
    def _load(self):
        '''
        Load history periods from the database.
        '''
        self._objects = []
        history_period_query = yield self.db.query_history_periods()

        for period in history_period_query:
            hist = HistoryPeriod(period[0], period[1], period[2], period[3])
            self._objects.append(hist)

class ControlType(Resource):
    '''
    This object represents a ControlType.
    '''
    def __init__(self, id, name):
        Resource.__init__(self)
        self.id = id
        self.name = name

    def json(self):
        return {"id": self.id, "name": self.name}

    def render_GET(self, request):
        return json.dumps(self.json())

class ControlTypes(HouseAgentREST):
    
    @inlineCallbacks
    def _load(self):
        '''
        Load control types from the database.
        '''
        self._objects = []
        control_type_query = yield self.db.query_controltypes()
        
        for control_type in control_type_query:
            hist = ControlType(control_type[0], control_type[1])
            self._objects.append(hist)

class Plugin_add(Resource):
    '''
    Template that adds a plugin to the database.
    '''    
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database
        
    def queryresult(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('plugin_add.html')
        self.request.write(str(template.render(locations=result))) 
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        self.db.query_locations().addCallback(self.queryresult)
        return NOT_DONE_YET  

class Plugin_add_do(Resource):
    '''
    Class that handles registration of a plugin in the database.
    '''
    def __init__(self, coordinator, database):
        Resource.__init__(self)
        self._coordinator = coordinator    
        self.db = database
    
    def plugin_registered(self, result):
        # Force reload of plug-ins
        self._coordinator.load_plugins()
        self.request.write(str(self.uuid))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request
        self.name = request.args["name"][0]
        location = request.args["location"][0]
        self.uuid = uuid4()
        def error(result):
            print "ERROR:", result
        
        self.db.register_plugin(self.name, self.uuid, location).addCallbacks(self.plugin_registered, error)
        return NOT_DONE_YET
    
class Plugin_status(Resource):
    '''
    Class that handles status overview of the plugins.
    '''
    def __init__(self, coordinator, database):
        Resource.__init__(self)
        self.coordinator = coordinator
        self.db = database

    def valueProccesor(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('plugin_status.html')
        
        status_result = []
        
        for plugin in result:
            temp = [plugin[0], plugin[1], plugin[2], False]
            
            for p in self.coordinator.plugins:
                if p.guid == plugin[1]:
                    temp[3] = p.online
            
            status_result.append(temp)       
        
        self.request.write(str(template.render(status_result=status_result))) 
        self.request.finish()  
    
    def render_GET(self, request):
        self.request = request
        self.db.query_plugins().addCallback(self.valueProccesor)
        return NOT_DONE_YET
    
class Device_add(Resource):
    '''
    Template that adds a advice to the database.
    '''    
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
        
    def finished(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('device_add.html')

        self.request.write(str(template.render(plugins=result[0], locations=result[1]))) 
        self.request.finish() 
    
    def render_GET(self, request):
        self.request = request

        deferredlist = []
        deferredlist.append(self.db.query_plugins())
        deferredlist.append(self.db.query_locations())
        
        d = defer.gatherResults(deferredlist)
        d.addCallback(self.finished)
        
        return NOT_DONE_YET  
    
class Device_list(Resource):
    '''
    Template that lists all the devices with values in the HouseAgent database.
    '''
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
    
    def finished(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('device_list.html')
        
        self.request.write(str(template.render(result=result[0], control_types=result[1]))) 
        self.request.finish()  
    
    def render_GET(self, request):
        self.request = request
        
        deferredlist = []
        deferredlist.append(self.db.query_values())
        deferredlist.append(self.db.query_controltypes())
        
        d = defer.gatherResults(deferredlist)
        d.addCallback(self.finished)
        return NOT_DONE_YET
    
class Device_management(Resource):
    '''
    Template that handles device management in the database.
    '''
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
        
    def result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('device_man.html')
        
        self.request.write(str(template.render(result=result)))
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        self.db.query_devices().addCallback(self.result)
        return NOT_DONE_YET
    
class Device_del(Resource):
    '''
    Class that handles adding of devices to the database.
    '''
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
            
    def device_deleted(self, result):
        self.request.write(str("done!"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request              
        id = request.args["id"][0]
        
        self.db.del_device(id).addCallback(self.device_deleted)
        return NOT_DONE_YET

class Event_create(Resource):
    """
    Template that creates a new event.
    """ 
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
    
    @inlineCallbacks  
    def finished(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('event_create.html')
        
        triggertypes = yield self.db.query_triggertypes()
        devs = yield self.db.query_devices_simple()
        conditiontypes = yield self.db.query_conditiontypes()
        
        self.request.write(str(template.render(trigger_types=triggertypes, devices=devs, action_types=result,
                                               condition_types=conditiontypes))) 
        self.request.finish()            
    
    def render_GET(self, request):
        self.request = request

        self.db.query_actiontypes().addCallback(self.finished)
        
        return NOT_DONE_YET

class Event_value_by_id(Resource):
    """
    Get's current values by device id from the database and returns a JSON dataset.
    """
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
    
    def jsonResult(self, results):
        output = dict()
        for result in results:
            output[result[0]] = result[1]
        
        self.request.write(str(json.dumps(output)))
        self.request.finish()        
    
    def render_GET(self, request):
        self.request = request
        deviceid = request.args["deviceid"][0]
        self.db.query_values_by_device_id(deviceid).addCallback(self.jsonResult)
        return NOT_DONE_YET 

class Event_actions_by_id(Resource):
    '''
    Get's possible actions for a value id.
    '''
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
    
    def result(self, device_type):
        
        output = {}
        if device_type[0][1] == "CONTROL_TYPE_THERMOSTAT":
            output[0] = "Set thermostat setpoint"
        elif device_type[0][0] == "CONTROL_TYPE_DIMMER":
            output[0] = "Set dim level"
        elif device_type[0][0] == "CONTROL_TYPE_ON_OFF":
            output[1] = "Power on"
            output[0] = "Power off"
        else:
            output[0] = "No actions available for this device"
        
        self.request.write(str(json.dumps(output)))
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        device_id = request.args["deviceid"][0]
        #db.query_device_type_by_device_id(device_id).addCallback(self.result)
        self.db.query_action_types_by_device_id(device_id).addCallback(self.result)
        return NOT_DONE_YET
    
class Event_control_types_by_id(Resource):
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
    
    def result(self, action_type):
        
        output = {}
        if action_type[0][0] == "CONTROL_TYPE_THERMOSTAT":
            output[0] = "Set thermostat setpoint"
        elif action_type[0][0] == "CONTROL_TYPE_DIMMER":
            output[0] = "Set dim level"
        elif action_type[0][0] == "CONTROL_TYPE_ON_OFF":
            output[1] = "Power on"
            output[0] = "Power off"
        else:
            output[0] = "No actions available for this device"
        
        self.request.write(str(json.dumps(output)))
        self.request.finish()

    def render_GET(self, request):
        self.request = request
        value_id = request.args["valueid"][0]
        self.db.query_action_type_by_value_id(value_id).addCallback(self.result)
        return NOT_DONE_YET    
    
class Event_control_values_by_id(Resource):
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
    
    def result(self, results):
        output = dict()
        for result in results:
            output[result[0]] = result[1]
        
        self.request.write(str(json.dumps(output)))
        self.request.finish() 

    def render_GET(self, request):
        self.request = request
        device_id = request.args["deviceid"][0]
        self.db.query_action_types_by_device_id(device_id).addCallback(self.result)
        return NOT_DONE_YET              

class Event_getvalue(Resource):
    """
    Get's a value's current value by value id (no I'm not drunk at the moment :-) )
    """
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
        
    def valueResult(self, result):
        self.request.write(str(result[0][0]))
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        valueid = request.args['valueid'][0]
        self.db.query_value_by_valueid(valueid).addCallback(self.valueResult)
        return NOT_DONE_YET
 
class Event_save(Resource):
    """
    Save's event to the database.
    """
    def __init__(self, eventengine, database):
        Resource.__init__(self)
        self.eventengine = eventengine    
        self.db = database
    
    def finished(self, result):
        self.eventengine.reload()
        self.request.write(str(result))
        self.request.finish()
    
    def render_POST(self, request):
       
        self.request = request
        event_info = json.loads(request.content.read())
            
        if event_info['enabled'] == "yes": 
            enabled = True
        else:
            enabled = False
            
        print "event_info", event_info

        self.db.add_event2(event_info["name"], enabled, event_info["conditions"], event_info["actions"], event_info["trigger"]).addCallback(self.finished)
        
        return NOT_DONE_YET

class GraphData(Resource):
    """
    Class to return historic data as json output.
    """
    def render_GET(self, request):
        
        self.request = request
        type = request.args["type"][0]
        period = request.args["period"][0]
        history_id = request.args["history_id"][0]
        
        if type == "gauge":
            rrd = RRD("history/%s.rrd" % history_id)
            result = rrd.fetch(resolution=60, start=period, end='now')
            
            clockfix = (datetime.datetime.now().hour - datetime.datetime.utcnow().hour) * 3600
            
            series = [((ts + clockfix) * 1000, val) for ts, val in result["data"]]
            
        return json.dumps(series)
    
class CreateGraph(Resource):
    """
    Template for creating a graph.
    """
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
    
    def result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('graph_create.html')
        
        self.request.write(str(template.render(result=result)))
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        self.db.query_historic_values().addCallback(self.result)
        return NOT_DONE_YET
    

class Control(Resource):
    """
    Class that manages device control.
    """
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
    
    def valueProcessor(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('control.html')
        
        self.request.write(str(template.render(result=result))) 
        self.request.finish()          
    
    def render_GET(self, request):
        self.request = request
        self.db.query_controllable_devices().addCallback(self.valueProcessor)
        return NOT_DONE_YET

class Control_onoff(Resource):
    """
    Class that manages on off actions.
    """
    def __init__(self, coordinator):
        Resource.__init__(self)
        self.coordinator = coordinator    
    
    def control_result(self, result):
        print "received:", result
        self.request.write(str(result['processed']))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request
        print "!!!!!!!!!!!"
        plugin = request.args["plugin"][0]
        address = request.args["address"][0]
        action = int(request.args["action"][0])
        
        if action == 1:
            self.coordinator.send_poweron(plugin, address).addCallback(self.control_result)
        elif action == 0:
            self.coordinator.send_poweroff(plugin, address).addCallback(self.control_result)
                    
        return NOT_DONE_YET
    
class Control_dimmer(Resource):
    '''
    Class that control dim levels of a dimmable lamp.
    '''
    def __init__(self, coordinator):
        Resource.__init__(self)
        self.coordinator = coordinator    
    
    def control_result(self, result):
        print "received:", result
        self.request.write(str(result['processed']))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request
        plugin = request.args["plugin"][0]
        address = request.args["address"][0]
        level = request.args["level"][0]

        self.coordinator.send_dimlevel(plugin, address, level).addCallback(self.control_result)
                    
        return NOT_DONE_YET    
    
class Control_stat(Resource):
    '''
    Class that control thermostat setpoint values.
    '''
    def __init__(self, coordinator):
        Resource.__init__(self)
        self.coordinator = coordinator    
    
    def control_result(self, result):
        print "received:", result
        self.request.write(str(result['processed']))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request
        plugin = request.args["plugin"][0]
        address = request.args["address"][0]
        temp = request.args["temp"][0]

        self.coordinator.send_thermostat_setpoint(plugin, address, temp).addCallback(self.control_result)
                    
        return NOT_DONE_YET    
 
class History(Resource):
    '''
    This turns value history on or off.
    '''
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
        
    def history_set(self, result):
        self.request.write(str("done!"))
        self.request.finish()        
    
    def render_POST(self, request):
        self.request = request
        id = request.args['id'][0]
        history = request.args['history'][0]
        
        if history == 'true':
            history=1
        elif history == 'false': 
            history=0

        print "history=", history
        
        self.db.set_history(int(id), history).addCallback(self.history_set)
        return NOT_DONE_YET
    
class Location_edited(Resource):
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database     
    
    def location_updated(self, result):
        self.request.write(str("success"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request
              
        name = request.args["name"][0]
        id = request.args["id"][0]
        try:
            parent = request.args["parent"][0]
        except KeyError:
            parent = None
       
        self.db.update_location(id, name, parent).addCallback(self.location_updated)
        return NOT_DONE_YET        
    
#class Plugins(Resource):
#    '''
#    Class that shows all the plugins in the database, and that allows plugin management.
#    '''
#    def __init__(self, database):
#        Resource.__init__(self)
#        self.db = database    
#    
#    def result(self, result):
#        lookup = TemplateLookup(directories=[houseagent.template_dir])
#        template = lookup.get_template('plugins.html')
#        
#        self.request.write(str(template.render(result=result)))
#        self.request.finish()
#    
#    def render_GET(self, request):
#        self.request = request
#        self.db.query_plugins().addCallback(self.result)
#        return NOT_DONE_YET

class Plugin_del(Resource):
    '''
    Class that handles deletion of plugins from the database.
    '''
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database     
    
    def plugin_deleted(self, result):
        self.request.write(str("done!"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request              
        id = request.args["id"][0]
        
        self.db.del_plugin(int(id)).addCallback(self.plugin_deleted)
        return NOT_DONE_YET
    
class Plugin_edit(Resource):
    '''
    Class that edits a plugin.
    '''
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database     
    
    @inlineCallbacks
    def plugin_result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('plugin_edit.html')
        
        locations = yield self.db.query_locations()
        
        print locations
        print result
        
        self.request.write( str( template.render(plugin=result, locations=locations ) ) ) 
        self.request.finish()            
    
    def render_GET(self, request):
        self.request = request
        id = request.args["id"][0]
        
        self.db.query_plugin(int(id)).addCallback(self.plugin_result)
        
        return NOT_DONE_YET
    
class Plugin_edited(Resource):
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database     
    
    def plugin_updated(self, result):
        self.request.write(str("success"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request
              
        name = request.args["name"][0]
        id = request.args["id"][0]
        
        try:
            location = request.args["location"][0]
        except KeyError:
            location = None
       
        self.db.update_plugin(id, name, location).addCallback(self.plugin_updated)
        return NOT_DONE_YET    
    
class Device_edit(Resource):
    '''
    Class that edits a device.
    '''
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 
    
    @inlineCallbacks
    def device_result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('device_edit.html')
        
        locations = yield self.db.query_locations()
        plugins = yield self.db.query_plugins()
        
        self.request.write( str( template.render(device=result, locations=locations, plugins=plugins ) ) ) 
        self.request.finish()            
    
    def render_GET(self, request):
        self.request = request
        id = request.args["id"][0]
        
        self.db.query_device(int(id)).addCallback(self.device_result)
        
        return NOT_DONE_YET
    
class Device_save(Resource):
    '''
    This web page saves a device in the HouseAgent database.
    '''
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database     
    
    def device_saved(self, result):
        self.request.write(str("done!"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request
              
        name = request.args["name"][0]
        address = request.args["address"][0]
        plugin = request.args["plugin"][0]
        location = request.args["location"][0]

        try:
            id = request.args["id"][0]
        except KeyError:
            id = None
        
        self.db.save_device(name, address, plugin, location, id).addCallback(self.device_saved)
        return NOT_DONE_YET
    
class Event(object):
    '''
    Skeleton class for event information.
    '''
    def __init__(self, id, name, enabled):
        self.id = id
        self.name = name
        self.enabled = enabled
        
    def __str__(self):
        return 'id: [{0}] name: [{1}] enabled: {2}'.format(self.id, self.name, self.enabled)

class Events(Resource):
    '''
    Class that shows all the events in the database, and that allows event management.
    '''
    def __init__(self, database):
        Resource.__init__(self)
        self.db = database 

    @inlineCallbacks
    def result(self, result):
        # Reuse skeleton classes from event engine
        from houseagent.core.events import Trigger, Condition, Action         
        events = []
        triggers = []
        conditions_out = []
        actions = []
        
        for event in result:
            e = Event(event[0], event[1], bool(event[2]))
            events.append(e)
        
        trigger_query = yield self.db.query_triggers()

        for trigger in trigger_query:   
            t = Trigger(trigger[1], trigger[2], trigger[3])
            
            # get trigger parameters
            trigger_parameters = yield self.db.query_trigger_parameters(trigger[0])
            
            for param in trigger_parameters:
                if param[0] == "cron":
                    
                    days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
                    cron = param[1].split(' ')
                    cron_text = 'Triggered every {0} at {1}:{2}'.format(
                        ','.join(days[int(n)] for n in cron[4].split(',')),
                        cron[1], cron[0])
                    
                    t.cron = cron_text
                elif param[0] == "current_value_id":
                    t.current_value_id = param[1]
                elif param[0] == "condition":
                    conditions = {"eq" : "is equal to",
                                  "ne" : "is not equal to",
                                  "lt" : "is less then",
                                  "gt" : "is greater then"}
                    
                    t.condition = conditions[param[1]]
                elif param[0] == "condition_value":
                    t.condition_value = param[1]
                    
            if t.type == "Device value change":
                extra = yield self.db.query_extra_valueinfo(t.current_value_id)
                
                t.device = extra[0][0]
                t.value = extra[0][1]
                                    
            triggers.append(t)
            
        condition_query = yield self.db.query_conditions()
        
        for condition in condition_query:
            c = Condition(condition[1], condition[2])
            
            condition_parameters = yield self.db.query_condition_parameters(condition[0])
            
            for param in condition_parameters:
                if param[0] == "condition":
                    conditions = {"eq" : "must be equal to",
                                  "ne" : "must not be equal to",
                                  "lt" : "must be less then",
                                  "gt" : "must be greater then"}                    
                    c.condition = conditions[param[1]]
                elif param[0] == "condition_value":
                    c.condition_value = param[1]
                elif param[0] == "current_values_id":
                    c.current_values_id = param[1]

            if c.type == "Device value":
                extra = yield self.db.query_extra_valueinfo(c.current_values_id)
                
                c.device = extra[0][0]
                c.value = extra[0][1]                

            conditions_out.append(c)  
            
        actions_query = yield self.db.query_actions()
        print "actions: " + str(actions_query)

        for action in actions_query:
            a = Action(action[1], action[2])
            
            action_parameters = yield self.db.query_action_parameters(action[0])
            for param in action_parameters:
                if param[0] == "device":
                    device = yield self.db.query_device(param[1])
                    a.device = device[0][1]
                elif param[0] == "control_value":
                    extra = yield self.db.query_extra_valueinfo(param[1])
                    a.control_value = param[1]
                    a.control_value_name = extra[0][1]
                elif param[0] == "command":
                    if param[1] == "1": a.command = "on"
                    elif param[1] == "0": a.command = "off"
                    else:
                        a.command = param[1]
                
            if action[1] == "Device action":               
                # fetch control_type
                control_type = yield self.db.query_controltypename(a.control_value)
                print "Control type" + str(control_type)
                a.control_type = control_type[0][0]
            
            actions.append(a)      

        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('events.html')
        
        self.request.write(str(template.render(events=events, triggers=triggers, conditions=conditions_out,
                                               actions=actions)))
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        self.db.query_events().addCallback(self.result)
        return NOT_DONE_YET
    
class Event_del(Resource):
    '''
    Class that handles deletion of events from the database.
    '''
    def __init__(self, eventengine, database):
        Resource.__init__(self)
        self.eventengine = eventengine
        self.db = database
    
    def event_deleted(self, result):
        self.eventengine.reload()
        self.request.write(str("done!"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request              
        id = request.args["id"][0]
        
        self.db.del_event(int(id)).addCallback(self.event_deleted)
        return NOT_DONE_YET
