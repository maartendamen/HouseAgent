import json
import time
from txZMQ import ZmqFactory, ZmqEndpoint, ZmqEndpointType, ZmqConnection
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater
from twisted.internet import reactor, defer
from zmq.core import constants

class Broker(ZmqConnection):
    '''
    This class is a custom implementation of custom ZmqConnection class.
    It is used to create a central broker for HouseAgent.
    '''
    socketType = constants.XREP
    
    def __init__(self, factory, coordinator, *endpoints):
        '''
        Intializer
        @param factory: a ZmqFactory instance.
        @param coordinator: a Coordinator instance.
        
        @return: Nothing
        '''
        ZmqConnection.__init__(self, factory, *endpoints)
        self.coordinator = coordinator
        self.message_id = 0
        self.requests = {}
    
    def messageReceived(self, msg):
        '''
        This function is called when a ZMQ message has been received.
        @param msg: the raw message that has been received
        
        @return: Nothing
        '''
        self.coordinator.log.debug("Coordinator::Raw ZMQ message received: %r" % (msg))
        
        routing_info = msg[0]
        type = msg[2]
        payload = msg[3:]

        if type == '\x05':
            # Handle RPC replies within this broker class.
            self.handle_rpc_reply(payload)
        else:
            try:
                fnc = self.coordinator.plugin_cmds[type]
                fnc(routing_info, payload)
            except KeyError:
                self.coordinator.log.error("Coordinator::Unhandled network response received: %r" % (msg))
    
    def send_rpc(self, routing_info, message):       
        '''
        This function sends a RPC message to a specified plugin.
        @param routing_info: the routing information of the plugin
        @param message: the message to send
        
        @return a Twisted deferred.
        '''
        d = defer.Deferred()
        message_id = self.get_next_id()
        self.requests[message_id] = d
        message = [routing_info, b'', chr(4), message_id, json.dumps(message)]

        self.coordinator.log.debug("Coordinator::Sending RPC message:%r" % (message))
        self.send(message)
        
        return d
    
    def handle_rpc_reply(self, payload):
        '''
        This function handles a received RPC reply.
        @param payload: the payload to process
        
        @return: nothing
        '''
        self.coordinator.log.debug("Coordinator::Received RPC reply: %r" % (payload))
        message_id = payload[0]
        payload = payload[1]
        
        d = self.requests.pop(message_id)
        d.callback(json.loads(payload))
    
    def get_next_id(self):
        '''
        Get a unique message ID.
        
        @return: a unique message ID
        '''
        return 'msg_id_%d' % (self.message_id + 1,)

class Coordinator(object):
    '''
    This class represents the network coordinator for HouseAgent.
    '''
    
    def __init__(self, log, database):
        '''
        Initialize the Coordinator
        @param log: a reference to the HouseAgent logger
        @param database: an instance of the HouseAgent database
        
        @return: nothing
        '''
        self.factory = ZmqFactory()
        self.log = log
        self.db = database
        self.plugins = []
        self.crud_callbacks = []
        self.eventengine = None
        
        self.plugin_cmds = { '\x01': self.handle_plugin_ready,
                             '\x02': self.handle_plugin_heartbeat,
                             '\x03': self.handle_plugin_value_update}
        
        # Startup actions
        self.load_plugins()
        self.db.coordinator = self
    
    def init_broker(self, host='*', port=13001):
        '''
        Initialize a new broker instance
        @param host: the hostname to listen on
        @param port: the port to listen on
        
        @return: nothing
        '''
        self.broker = Broker(self.factory, self, ZmqEndpoint(ZmqEndpointType.Bind, 'tcp://%s:%s' % (host, port)))

    def handle_plugin_ready(self, routing_info, payload):
        '''
        This function handles ready messages received on the broker.
        
        @param routing_info: the routing information associated with the plugin
        @param payload: the payload, such as the plugin guid and possible callbacks
        
        @return: nothing
        '''
        self.log.debug("Coordinator::Received plugin ready message from: %r" % (payload[0]) )

        found = False

        for plugin in self.plugins:
            if plugin.guid == payload[0]:
                self.log.debug("Coordinator::Plugin found in database, setting status to online...")
                found = True
                plugin.online = True
                plugin.type = payload[1]
                plugin.routing_info = routing_info
                
                # Register callbacks
                plugin.callbacks = json.loads(payload[2])                    
        
        if not found:
            self.log.warning("Coordinator::Plugin not found in database! Check your plugin GUID...")
                
    def handle_plugin_heartbeat(self, routing_info, payload):
        '''
        This function handles heartbeat messages received from plugins on the broker.
        
        @param routing_info: the routing information associated with the plugin
        @param payload: the payload, nothing in the case of a heartbeat
        
        @return: nothing
        '''
        self.log.debug("Coordinator::Received plugin heartbeat...")
        found = False
        
        for plugin in self.plugins:
            if plugin.routing_info == routing_info and plugin.online:
                found = True
                self.log.debug("Coordinator::Found plugin routing information and plugin is ready, heartbeat accepted...")
                plugin.time = time.time()
        
        if not found:
            self.log.debug("Coordinator::Plugin is not ready, asking plugin about ready status...")
            message = [routing_info, b'', chr(1)]
            self.broker.send(message)
                
    @inlineCallbacks
    def handle_plugin_value_update(self, routing_info, payload):
        '''
        This function handles plugin value updates. 
        
        @param routing_info: the routing information associated with the plugin
        @param payload: the payload, such as the device values and value labels
        '''
        self.log.debug("Coordinator::Received plugin value update...")
        
        for plugin in self.plugins:
            if plugin.routing_info == routing_info:
                message = json.loads(payload[0])
                self.log.debug("Coordinator::Decoded update, sending to database: %r " % (message))
                
                for key in message["values"]:
                    value_id = yield self.db.update_or_add_value(key, message["values"][key], 
                                                plugin.id, 
                                                message["address"], message["time"])

                    # Notify the eventengine
                    if self.eventengine:
                        self.eventengine.device_value_changed(value_id, message["values"][key])
                        
    def send_custom(self, plugin_id, action, parameters):
        '''
        Send custom command to a plugin
        
        @param plugin_id: the id of the plugin
        @param action: the action to send
        @param parameters: the parameters for the action
        
        @return: a Twisted deferred which will callback with the result
        '''
        
        content = {'action': action, 
                   'parameters': parameters,
                   'type': 'custom'}
        
        return self.send_command(plugin_id, content)
    
    def send_poweron(self, plugin_id, address):
        '''
        Send power on request to device.
        @param plugin_id: the id of the plugin
        @param address: the address of the device
        
        @return: a Twisted deferred which will callback with the result
        '''
        content = {'address': address,
                   'type': 'poweron'}
        
        return self.send_command(plugin_id, content)
        
    def send_poweroff(self, plugin_id, address):
        '''
        Send power off request to device.
        @param plugin_id: the id of the plugin
        @param address: the address of the device
        
        @return: a Twisted deferred which will callback with the result
        '''
        content = {'address': address,
                   'type': 'poweroff'}
        
        return self.send_command(plugin_id, content)
        
    def send_thermostat_setpoint(self, plugin_id, address, temperature):
        '''
        Send thermostat setpoint request to specified device.
        @param plugin_id: the id of the plugin
        @param address: the address of the device
        @param temperature: the tempreature to set
        
        @return: a Twisted deferred which will callback with the result
        '''
        content = {'address': address,
                   'type': 'thermostat_setpoint', 
                   'temperature': temperature}
        
        return self.send_command(plugin_id, content)

    def send_command(self, plugin_id, content):
        '''
        Send command to specified plugin_id
        
        @param plugin_id: the ID of the plugin
        @param content: the content to send
        '''
        p = self.plugin_by_guid(plugin_id)
        if p:
            return self.broker.send_rpc(p.routing_info, content)
        else:
            return None
        
    def send_crud_update(self, type, action, parameters):
        '''
        This function sends an update to the broker after a CRUD operation took place.
        Plugins can subcribe to these kind of messages to handle within their plugin.
        @param type: the update type, for example device update have the device update type
        @param action: the CRUD action, for example update, delete, creation
        @param parameters: the parameters specified with the CRUD action, for example a device ID
        '''
        content = {"type": type,
                   "action": action, 
                   "parameters": parameters}
        
        for p in self.plugins:
            if 'crud' in p.callbacks and p.online:
                message = [p.routing_info, b'', chr(6), json.dumps(content)]
                self.broker.send(message)
                           
    @inlineCallbacks
    def load_plugins(self):
        '''
        This function loads plugin information from the HouseAgent database.
        '''
        # Empty in case of a reload
        self.plugins = []
        
        plugins = yield self.db.query_plugins()
        for plugin in plugins:
            p = Plugin(plugin[1], plugin[2], time.time())
            self.plugins.append(p)
           
    def plugin_id_by_guid(self, guid):
        '''
        This helper function returns a plugin_id based upon a plugin's GUID.
        @param guid: the plugin guid
        
        @return: returns a Plugin ID 
        '''
        for p in self.plugins:
            if p.guid == guid:
                return p.id
            
    def plugin_by_id(self, id):
        '''
        Return a plugin object identified by ID.
        @param id: the id of the plugin
        
        @return: None if nothing is found, otherwise Plugin()
        '''
        for p in self.plugins:
            if p.id == id:
                return p
            
        return None
    
    def plugin_by_guid(self, guid):
        '''
        Return a plugin object identified by GUID.
        @param guid: the guid of the plugin
        
        @return: None if nothing is found, otherwise Plugin()
        '''
        for p in self.plugins:
            if p.guid == guid:
                return p
            
        return None
    
    def get_plugins_by_type(self, type):
        '''
        Returns a list of plugins specified by type.
        @param type: the type of plugin
        
        @return: a list of plugins
        '''
        output = []
        for p in self.plugins:

            if p.type == type:
                output.append(p)
        
        return output
                
class Plugin(object):
    '''
    This is a skeleton class for a network plugin.
    '''
    
    def __init__(self, guid, id, time):
        '''
        Initialize a new Plugin instance.
        
        @param guid: the guid of the plugin
        @param id: the id of the plugin
        @param time: last update time of the plugin
        '''
        self.guid = guid
        self.id = id
        self.time = time
        self.online = False
        self.type = None
        self.routing_info = None
        self.callbacks = []
        
    def __str__(self):
        ''' A string representation of the Plugin object '''
        return "guid: %s, id: %s, time: %s, online: %s, type: %s, routing_info: %r" % (self.guid, self.id, self.time, 
                                                                                       self.online, self.type, self.routing_info)
