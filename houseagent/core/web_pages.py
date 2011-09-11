from houseagent.core import database
from pyrrd.rrd import RRD
from mako.lookup import TemplateLookup
from mako.template import Template
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from uuid import uuid4
import houseagent
import datetime
import json

# Create database instance
db = database.Database()

class Root(Resource):
    '''
    This is the main page for HouseAgent.
    '''
    def render_GET(self, request):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('index.html')
        return str(template.render())

class Plugin_add(Resource):
    '''
    Template that adds a plugin to the database.
    '''    
    def queryresult(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('plugin_add.html')
        self.request.write( str( template.render(locations=result) ) ) 
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        db.query_locations().addCallback(self.queryresult)
        return NOT_DONE_YET  

class Plugin_add_do(Resource):
    '''
    Class that handles registration of a plugin in the database.
    '''
    def __init__(self, coordinator):
        Resource.__init__(self)
        self._coordinator = coordinator    
    
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
        
        db.register_plugin(self.name, self.uuid, location).addCallbacks(self.plugin_registered, error)
        return NOT_DONE_YET
    
class Plugin_status(Resource):
    '''
    Class that handles status overview of the plugins.
    '''
    def __init__(self, coordinator):
        Resource.__init__(self)
        self._coordinator = coordinator

    def valueProccesor(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('plugin_status.html')
        
        status_result = []
        
        for plugin in result:
            temp = [plugin[0], plugin[1], plugin[2], False]
            
            for p in self._coordinator._plugins:
                if p.guid == plugin[1]:
                    temp[3] = p.online
            
            status_result.append(temp)       
        
        self.request.write(str(template.render(status_result=status_result))) 
        self.request.finish()  
    
    def render_GET(self, request):
        self.request = request
        db.query_plugins().addCallback(self.valueProccesor)
        return NOT_DONE_YET
    
class Device_add(Resource):
    '''
    Template that adds a advice to the database.
    '''    
    def finished(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('device_add.html')

        self.request.write(str(template.render(plugins=result[0], locations=result[1]))) 
        self.request.finish() 
    
    def render_GET(self, request):
        self.request = request

        deferredlist = []
        deferredlist.append(db.query_plugins())
        deferredlist.append(db.query_locations())
        
        d = defer.gatherResults(deferredlist)
        d.addCallback(self.finished)
        
        return NOT_DONE_YET  
    
class Device_add_do(Resource):
    '''
    Class that handles adding of devices to the database.
    '''
    def device_added(self, result):
        self.request.write(str("done!"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request
              
        name = request.args["name"][0]
        address = request.args["address"][0]
        plugin = request.args["plugin"][0]
        location = request.args["location"][0]
        
        db.add_device(name, address, plugin, location).addCallback(self.device_added)
        return NOT_DONE_YET
    
class Device_list(Resource):
    '''
    Template that lists all the devices with values in the HouseAgent database.
    '''
    def finished(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('device_list.html')
        
        self.request.write(str(template.render(result=result[0], control_types=result[1]))) 
        self.request.finish()  
    
    def render_GET(self, request):
        self.request = request
        
        deferredlist = []
        deferredlist.append(db.query_values())
        deferredlist.append(db.query_controltypes())
        
        d = defer.gatherResults(deferredlist)
        d.addCallback(self.finished)
        return NOT_DONE_YET
    
class Device_management(Resource):
    '''
    Template that handles device management in the database.
    '''
    def result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('device_man.html')
        
        self.request.write(str(template.render(result=result)))
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        db.query_devices().addCallback(self.result)
        return NOT_DONE_YET
    
class Device_del(Resource):
    '''
    Class that handles adding of devices to the database.
    '''
    def device_deleted(self, result):
        self.request.write(str("done!"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request              
        id = request.args["id"][0]
        
        db.del_device(id).addCallback(self.device_deleted)
        return NOT_DONE_YET
    
class Latitude_locations(Resource):
    """
    Class that displays latitude locations.
    """
    def __init__(self, databus):
        Resource.__init__(self)
        self.databus = databus
        
    def result(self, result):
        lookup = TemplateLookup(directories=['templates/'])
        template = Template(filename='templates/plugins/latitude/known_locations.html', lookup=lookup)
        
        self.request.write(str(template.render(result=result)))
        self.request.finish()
        
    def queryresult(self, result):
        found = False
        
        active_plugins = []
        
        for plugin in result:
            temp = [plugin[0], plugin[1], plugin[2], False, plugin[3]]
            
            if plugin[2] == 'Google Latitude':
                found = True
            
            # Check availability
            for key in self.databus.databus.plugins:
                if self.databus.databus.plugins[key] == plugin[3]:
                    temp[3] = True
                    active_plugins.append(temp)
            
        if found == False:
            self.request.write(str("No plugins found in the database..."))
            self.request.finish()
            
        if len(active_plugins) == 1:
            print active_plugins
            self.databus.send_custom(active_plugins[0][4], "get_locations", {}).addCallback(self.result)
         
        if len(active_plugins) < 1:
            lookup = TemplateLookup(directories=['templates/'])
            template = Template(filename='templates/plugins/latitude/online_error.html', lookup=lookup)
            
            self.request.write(str(template.render()))
            self.request.finish()            
        #self.request.write(str("Active plugins; found in the database..."))
        #self.request.finish()                
    
    def render_GET(self, request):
        self.request = request
        #self.databus.send_custom(4, "get_locations", {}).addCallback(self.result)
        db.query_plugins().addCallback(self.queryresult)
        return NOT_DONE_YET

class Latitude_accounts(Resource):
    """
    Class that displays latitude accounts.
    """
    def __init__(self, databus):
        Resource.__init__(self)
        self.databus = databus
        
    def result(self, result):
        print result
        
        lookup = TemplateLookup(directories=['templates/'])
        template = Template(filename='templates/plugins/latitude/accounts.html', lookup=lookup)
        
        self.request.write(str(template.render(result=result)))
        self.request.finish()
        
    def queryresult(self, result):
        found = False
        
        active_plugins = []
        
        for plugin in result:
            temp = [plugin[0], plugin[1], plugin[2], False, plugin[3]]
            
            if plugin[2] == 'Google Latitude':
                found = True
            
            # Check availability
            for key in self.databus.databus.plugins:
                if self.databus.databus.plugins[key] == plugin[3]:
                    temp[3] = True
                    active_plugins.append(temp)
            
        if found == False:
            self.request.write(str("No plugins found in the database..."))
            self.request.finish()
            
        if len(active_plugins) == 1:
            print active_plugins
            self.databus.send_custom(active_plugins[0][4], "get_accounts", {}).addCallback(self.result)
         
        if len(active_plugins) < 1:
            lookup = TemplateLookup(directories=['templates/'])
            template = Template(filename='templates/plugins/latitude/online_error.html', lookup=lookup)
            
            self.request.write(str(template.render()))
            self.request.finish()              
    
    def render_GET(self, request):
        self.request = request
        #self.databus.send_custom(4, "get_locations", {}).addCallback(self.result)
        db.query_plugins().addCallback(self.queryresult)
        return NOT_DONE_YET
        
class Event_create(Resource):
    """
    Template that creates a new event.
    """ 
    
    @inlineCallbacks  
    def finished(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('event.html')
        
        triggertypes = yield db.query_triggertypes()
        devs = yield db.query_devices_simple()
        conditiontypes = yield db.query_conditiontypes()
        
        self.request.write(str(template.render(trigger_types=triggertypes, devices=devs, action_types=result,
                                               condition_types=conditiontypes, edit=False))) 
        self.request.finish()            
    
    def render_GET(self, request):
        self.request = request

        db.query_actiontypes().addCallback(self.finished)
        
        return NOT_DONE_YET
    
class Event_edit(Resource):
    """
    Template that allows editing of a device.
    """ 
    @inlineCallbacks  
    def finished(self, event):
        
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('event.html')
        
        triggertypes = yield db.query_triggertypes()
        devs = yield db.query_devices_simple()
        conditiontypes = yield db.query_conditiontypes()
        actiontypes = yield db.query_actiontypes()
        
        self.request.write(str(template.render(trigger_types=triggertypes, devices=devs, action_types=actiontypes,
                                               condition_types=conditiontypes, edit=True, event=event))) 
        self.request.finish()            
    
    def render_GET(self, request):
        self.request = request
        event_id = request.args["id"][0]
        db.query_event(event_id).addCallback(self.finished)
        return NOT_DONE_YET

class Event_value_by_id(Resource):
    """
    Get's current values by device id from the database and returns a JSON dataset.
    """
    def jsonResult(self, results):
        output = dict()
        for result in results:
            output[result[0]] = result[1]
        
        self.request.write(str(json.dumps(output)))
        self.request.finish()        
    
    def render_GET(self, request):
        self.request = request
        deviceid = request.args["deviceid"][0]
        db.query_values_by_device_id(deviceid).addCallback(self.jsonResult)
        return NOT_DONE_YET 

class Event_actions_by_id(Resource):
    '''
    Get's possible actions for a value id.
    '''
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
        db.query_action_types_by_device_id(device_id).addCallback(self.result)
        return NOT_DONE_YET
    
class Event_control_types_by_id(Resource):
    
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
        db.query_action_type_by_value_id(value_id).addCallback(self.result)
        return NOT_DONE_YET    
    
class Event_control_values_by_id(Resource):
    
    def result(self, results):
        output = dict()
        for result in results:
            output[result[0]] = result[1]
        
        self.request.write(str(json.dumps(output)))
        self.request.finish() 

    def render_GET(self, request):
        self.request = request
        device_id = request.args["deviceid"][0]
        db.query_action_types_by_device_id(device_id).addCallback(self.result)
        return NOT_DONE_YET              

class Event_getvalue(Resource):
    """
    Get's a value's current value by value id (no I'm not drunk at the moment :-) )
    """
    def valueResult(self, result):
        self.request.write(str(result[0][0]))
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        valueid = request.args['valueid'][0]
        db.query_value_by_valueid(valueid).addCallback(self.valueResult)
        return NOT_DONE_YET
 
class Event_save(Resource):
    """
    Save's event to the database.
    """
    def __init__(self, eventengine):
        Resource.__init__(self)
        self.eventengine = eventengine    
    
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

        db.add_event2(event_info["name"], enabled, event_info["conditions"], event_info["actions"], event_info["trigger"]).addCallback(self.finished)
        
        return NOT_DONE_YET
    
class Test(Resource):
    """
    Template for testing.
    """
    def render_GET(self, request):
        self.request = request
        
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('test.html')
        
        self.request.write(str(template.render())) 
        self.request.finish()

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
    def result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('graph_create.html')
        
        self.request.write(str(template.render(result=result)))
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        db.query_historic_values().addCallback(self.result)
        return NOT_DONE_YET
    

class Control(Resource):
    """
    Class that manages device control.
    """
    def valueProcessor(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('control.html')
        
        self.request.write(str(template.render(result=result))) 
        self.request.finish()          
    
    def render_GET(self, request):
        self.request = request
        db.query_controllable_devices().addCallback(self.valueProcessor)
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
    
class Location_add(Resource):
    '''
    Class that adds a room to the database.
    '''
    def got_locations(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('location_add.html')
        
        print result
        
        self.request.write( str( template.render(locations=result) ) ) 
        self.request.finish()        
    
    def render_GET(self, request): 
        self.request = request       
        db.query_locations().addCallback(self.got_locations)
        return NOT_DONE_YET
        
class Location_added(Resource):
    '''
    Class that actually adds a room to the database, and gives a callback to the caller.
    '''
    def room_added(self, result):
        self.request.write(str("success"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request
              
        name = request.args["name"][0]
        try:
            parent = request.args["parent"][0]
        except KeyError:
            parent = None
       
        db.add_location(name, parent).addCallback(self.room_added)
        return NOT_DONE_YET
    
class Locations(Resource):
    '''
    Class that shows all the rooms in the database, and that allows room management.
    '''
    def result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('locations.html')
        
        self.request.write(str(template.render(result=result)))
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        db.query_locations().addCallback(self.result)
        return NOT_DONE_YET
    
class Location_del(Resource):
    '''
    Class that handles deletion of locations from the database.
    '''
    def location_deleted(self, result):
        self.request.write(str("done!"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request              
        id = request.args["id"][0]
        
        db.del_location(int(id)).addCallback(self.location_deleted)
        return NOT_DONE_YET
    
class Location_edit(Resource):
    '''
    Class that edits a location.
    '''
    
    def location_result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('location_edit.html')
        
        self.request.write( str( template.render(locations=result[0], loc=result[1]) ) ) 
        self.request.finish()            
        
    def error(self, errorcode):
        print "ERROR: ", errorcode
    
    def render_GET(self, request):
        self.request = request
        id = request.args["id"][0]
        
        deferredlist = []
        deferredlist.append(db.query_locations())
        deferredlist.append(db.query_location(int(id)))
        
        d = defer.gatherResults(deferredlist)
        d.addCallbacks(self.location_result)
        
        return NOT_DONE_YET
    
class History(Resource):
    '''
    This turns value history on or off.
    '''
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
        
        db.set_history(int(id), history).addCallback(self.history_set)
        return NOT_DONE_YET     
    
class Control_type(Resource):
    '''
    This sets the control type for a value.
    '''
    def control_type_set(self, result):
        self.request.write(str("done!"))
        self.request.finish()        
    
    def render_POST(self, request):
        self.request = request
        id = request.args['id'][0]
        control_type = request.args['type'][0]
        
        db.set_controltype(int(id), int(control_type)).addCallback(self.control_type_set)
        return NOT_DONE_YET       
    
class Location_edited(Resource):
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
       
        db.update_location(id, name, parent).addCallback(self.location_updated)
        return NOT_DONE_YET        
    
class Plugins(Resource):
    '''
    Class that shows all the plugins in the database, and that allows plugin management.
    '''
    def result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('plugins.html')
        
        self.request.write(str(template.render(result=result)))
        self.request.finish()
    
    def render_GET(self, request):
        self.request = request
        db.query_plugins().addCallback(self.result)
        return NOT_DONE_YET

class Plugin_del(Resource):
    '''
    Class that handles deletion of plugins from the database.
    '''
    def plugin_deleted(self, result):
        self.request.write(str("done!"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request              
        id = request.args["id"][0]
        
        db.del_plugin(int(id)).addCallback(self.plugin_deleted)
        return NOT_DONE_YET
    
class Plugin_edit(Resource):
    '''
    Class that edits a plugin.
    '''
    
    @inlineCallbacks
    def plugin_result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('plugin_edit.html')
        
        locations = yield db.query_locations()
        
        print locations
        print result
        
        self.request.write( str( template.render(plugin=result, locations=locations ) ) ) 
        self.request.finish()            
    
    def render_GET(self, request):
        self.request = request
        id = request.args["id"][0]
        
        db.query_plugin(int(id)).addCallback(self.plugin_result)
        
        return NOT_DONE_YET
    
class Plugin_edited(Resource):
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
       
        db.update_plugin(id, name, location).addCallback(self.plugin_updated)
        return NOT_DONE_YET    
    
class Device_edit(Resource):
    '''
    Class that edits a device.
    '''
    
    @inlineCallbacks
    def device_result(self, result):
        lookup = TemplateLookup(directories=[houseagent.template_dir])
        template = lookup.get_template('device_edit.html')
        
        locations = yield db.query_locations()
        plugins = yield db.query_plugins()
        
        self.request.write( str( template.render(device=result, locations=locations, plugins=plugins ) ) ) 
        self.request.finish()            
    
    def render_GET(self, request):
        self.request = request
        id = request.args["id"][0]
        
        db.query_device(int(id)).addCallback(self.device_result)
        
        return NOT_DONE_YET
    
class Device_save(Resource):
    '''
    This web page saves a device in the HouseAgent database.
    '''
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
        
        db.save_device(name, address, plugin, location, id).addCallback(self.device_saved)
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
        
        trigger_query = yield db.query_triggers()

        for trigger in trigger_query:   
            t = Trigger(trigger[1], trigger[2], trigger[3])
            
            # get trigger parameters
            trigger_parameters = yield db.query_trigger_parameters(trigger[0])
            
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
                extra = yield db.query_extra_valueinfo(t.current_value_id)
                
                t.device = extra[0][0]
                t.value = extra[0][1]
                                    
            triggers.append(t)
            
        condition_query = yield db.query_conditions()
        
        for condition in condition_query:
            c = Condition(condition[1], condition[2])
            
            condition_parameters = yield db.query_condition_parameters(condition[0])
            
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
                extra = yield db.query_extra_valueinfo(c.current_values_id)
                
                c.device = extra[0][0]
                c.value = extra[0][1]                

            conditions_out.append(c)  
            
        actions_query = yield db.query_actions()
        print "actions: " + str(actions_query)

        for action in actions_query:
            a = Action(action[1], action[2])
            
            action_parameters = yield db.query_action_parameters(action[0])
            for param in action_parameters:
                if param[0] == "device":
                    device = yield db.query_device(param[1])
                    a.device = device[0][1]
                elif param[0] == "control_value":
                    extra = yield db.query_extra_valueinfo(param[1])
                    a.control_value = param[1]
                    a.control_value_name = extra[0][1]
                elif param[0] == "command":
                    if param[1] == "1": a.command = "on"
                    elif param[1] == "0": a.command = "off"
                    else:
                        a.command = param[1]
                
            if action[1] == "Device action":               
                # fetch control_type
                control_type = yield db.query_controltypename(a.control_value)
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
        db.query_events().addCallback(self.result)
        return NOT_DONE_YET
    
class Event_del(Resource):
    '''
    Class that handles deletion of events from the database.
    '''
    def __init__(self, eventengine):
        Resource.__init__(self)
        self.eventengine = eventengine     
    
    def event_deleted(self, result):
        self.eventengine.reload()
        self.request.write(str("done!"))
        self.request.finish()
    
    def render_POST(self, request):
        self.request = request              
        id = request.args["id"][0]
        
        db.del_event(int(id)).addCallback(self.event_deleted)
        return NOT_DONE_YET
