from txZMQ import ZmqFactory, ZmqEndpoint, ZmqSubConnection, ZmqEndpointType
from txZMQ.xreq_xrep import ZmqXREQConnection
import json
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater
from twisted.internet import reactor
import time

class Coordinator(object):
    '''
    This is the network coordinator for HouseAgent.
    '''
    def __init__(self, log, database):
        self.factory = ZmqFactory()
        self.log = log
        self.db = database
        self.plugins = []
        self.eventengine = None
        
        # Startup actions
        self.load_plugins()
        
        def test_reply(result):
            self.log.debug("Coordinator::Received RPC reply: %r" % (result, ))
        
        self.test = PluginRPC(self.factory, '127.0.0.1', 13002)        
        deferLater(reactor, 10.0, self.test.send_request, 'custom', 'LALALA').addCallback(test_reply)
    
    def init_collector(self, host='*', port=13001):
        '''
        This function initializes the HouseAgent collector. 
        The collector is used to gather published messages from plugins.
        This is used for example to receive value updates.
        @param host: the host/IP to listen on, defaults to any (*)
        @param port: the port to listen on, defaults to 13001
        '''
        self.log.debug("Coordinator::Setting up collector...")
        endpoint = ZmqEndpoint('bind', 'tcp://%s:%s' % (host, port) )

        socket = ZmqSubConnection(self.factory, endpoint)
        socket.subscribe("")

        socket.gotMessage = self.handle_collector_message
        self.log.debug("Coordinator::Finished setting up collector...")

    def handle_collector_message(self, *msg):
        '''
        Handle a message received on the collector socket.
        @param *msg: the received message
        '''
        self.log.debug("Coordinator::Received collector message: %r" % (msg, ))
        
        try:
            tag = msg[1]
            message = msg[0]
        except:
            return
        
        if tag == 'value_update':
            self.handle_value_update(message)
        elif tag == 'network':
            self.handle_network_update(message)
    
    @inlineCallbacks
    def handle_value_update(self, message):
        '''
        This function handles value updates received by the collector.
        @param message: 
        '''
        self.log.debug("Coordinator::Received value update: %r" % (message))
        message = json.loads(message)
        
        for key in message["values"]:
            value_id = yield self.db.update_or_add_value(key, message["values"][key], 
                                        self.plugin_id_by_guid(message["plugin_id"]), 
                                        message["address"], message["time"])
                                
            # Notify the eventengine
            if self.eventengine:
                self.eventengine.device_value_changed(value_id, message["values"][key])
                
    def handle_network_update(self, message):
        '''
        This function handles network updates received by the collector.
        @param message:
        '''
        self.log.debug("Coordinator::Received network update: %r" % (message))
        message = json.loads(message)
        for p in self.plugins:
            if p.guid == message["id"]:
                p.online = True
                p.time = time.time()
                p.type = message["type"]
                
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
        '''
        for p in self.plugins:
            if p.guid == guid:
                return p.id
                
class Plugin(object):
    '''
    This is a skeleton class for a network plugin.
    '''
    def __init__(self, guid, id, time):
        self.guid = guid
        self.id = id
        self.time = time
        self.online = False
        self.type = None
        
    def __str__(self):
        return "guid: %s, id: %s, time: %s, online: %s, type: %s" % (self.guid, self.id, self.time, 
                                                                     self.online, self.type)

class PluginRPC(object):
    '''
    This class represents a plugin RPC connection.
    '''
    def __init__(self, factory, host, port):
       
        self.socket = ZmqXREQConnection(factory, ZmqEndpoint(ZmqEndpointType.Bind, 'tcp://%s:%s' % (host, port)))
        self.socket.get_next_id = self.get_next_id
        
        self.count = 0

    def get_next_id(self):
        return 'msg_id_%d' % (self.count + 1,)

    def send_request(self, *message):
        return self.socket.sendMsg(*message)
       
#class Coordinator(object):
#    '''
#    This is the network coordinator for HouseAgent.
#    ''' 
#    def __init__(self, coordinator_name=None, broker_ip='127.0.0.1', broker_port=5672, username='guest', password='guest', vhost='/'):
#        
#        self._logging = True
#        
#        self.db = Database()
#        self._plugins = []
#        self._request_id = 0
#        self._outstanding_requests = {}
#        self._eventengine = None
#        
#        self._broker_host = broker_ip
#        self._broker_port = broker_port
#        self._broker_user = username
#        self._broker_pass = password
#        self._broker_vhost = vhost
#
#        self._qname = coordinator_name
#        self._tag = 'mq%d' % id(self)
#
#        self.load_plugins()
#            
#        self._connect_client()
#    
#    def log(self, msg):
#        '''
#        This logs a message to the HouseAgent log.
#        '''
#        if self._logging:
#            log.msg(msg)
#    
#    @inlineCallbacks
#    def _connect_client(self):
#        '''
#        Sets up a client connection to the RabbitMQ broker.
#        '''        
#        # Check locally, when running in developer mode
#        if os.path.exists("specs/amqp0-8.xml"):
#            spec = txamqp.spec.load("specs/amqp0-8.xml")
#        # Check in /etc/HouseAgent when deployed.
#        elif os.path.exists("/etc/HouseAgent/amqp0-8.xml"):
#            spec = txamqp.spec.load("/etc/HouseAgent/amqp0-8.xml")
#        try:
#            client = yield ClientCreator(reactor, AMQClient, TwistedDelegate(), self._broker_vhost, spec).connectTCP(self._broker_host, int(self._broker_port))
#        except ConnectionRefusedError:            
#            self.log("Failed to connect to RabbitMQ broker.. retrying..")
#            reactor.callLater(10.0, self._connect_client)
#            return
#        except Exception, e:
#            self.log("Unhandled exception while connecting to RabbitMQ broker: %s" % e)
#          
#        self.log("Connected to RabbitMQ broker, authenticating...")
#        yield client.authenticate(self._broker_user, self._broker_pass)
#        self._setup(client)
#    
#    @inlineCallbacks
#    def _setup(self, client):
#        '''
#        This sets up all the communication channels with the broker.
#        '''        
#        self._client = client
#        
#        # Channel setup
#        try:
#            self._channel = yield self._client.channel(1)
#        except:
#            self.log("Error setting up RabbitMQ communication channel!")            
#    
#        try:
#            yield self._channel.channel_open()
#        except:
#            self.log("Error opening RabbitMQ communication channel!")
#    
#        # Declare exchange
#        try:
#            yield self._channel.exchange_declare(exchange="houseagent.direct", type="direct", durable="True")
#        except:
#            self.log("Error declaring RabbitMQ exchange!")
#            
#        # Declare queue
#        try:
#            yield self._channel.queue_declare(queue=self._qname, durable=True)
#        except:
#            self.log("Error declaring RabbitMQ queue!")
#            
#        # Bind queue
#        try:
#            yield self._channel.queue_bind(queue=self._qname, exchange="houseagent.direct",
#                                     routing_key="value_updates")
#            yield self._channel.queue_bind(queue=self._qname, exchange="houseagent.direct",
#                                     routing_key="network")
#        except:
#            self.log("Error binding RabbitMQ queue's!")
#
#        # Set-up consumer
#        try:
#            self._channel.basic_consume(queue=self._qname, no_ack=True,
#                                        consumer_tag=self._tag)
#        except:
#            self.log("Error setting up RabbitMQ consumer!")
#
#        # Start receiving message from the broker
#        self.log("Succesfully setup RabbitMQ broker connection...")
#        self._client.queue(self._tag).addCallback(lambda queue: self.handle_msg(None, queue))                    
#        
#        # This checks all plugins every 10 seconds
#        l.start(10.0)
#    
#    def _check_plugins(self):
#        '''
#        This checks all plugins for availability.
#        A network ping must be received within 60 seconds, otherwise the plugin
#        will be marked as unavailable.
#        '''
#        for p in self._plugins:
#            if time.time() - p.time > 60:
#                p.online = False
#    
#    def handle_err(self, failure, queue):
#        '''
#        This handles message get errors. 
#        '''
#        if failure.check(Closed):
#            self._connect_client()
#        else:
#            print 'error: %s' % failure
#            self.handle_msg(None, queue)
#
#    def setup_error(self, failure):
#        print 'ERROR: failed to create RPC Receiver: %s' % failure
#
#    @inlineCallbacks
#    def load_plugins(self):
#        '''
#        This function loads plug-in information from the HouseAgent database.
#        '''
#        # Empty in case of a reload
#        self._plugins = []
#        
#        plugins = yield self.db.query_plugins()
#        for plugin in plugins:
#            p = Plugin(plugin[1], plugin[2], time.time())
#            self._plugins.append(p)       
#            
#    def send_custom(self, plugin_id, action, parameters):
#        '''
#        Send custom plugin command to a plugin.
#        '''
#        print "sending custom command:", plugin_id, action, parameters
#        
#        content = {'action': action,
#                   'parameters': parameters, 
#                   'type': 'custom'}
#        
#        self._request_id += 1
#        
#        msg = Content(json.dumps(content))
#        msg["delivery mode"] = 1
#        msg['correlation id'] = str(self._request_id)
#        msg['reply to'] = self._qname
#
#        self._channel.basic_publish(exchange="houseagent.direct", content=msg, routing_key=plugin_id)
#        
#        # create new deferred
#        d = defer.Deferred()
#        self._outstanding_requests[self._request_id] = d
#        return d
#    
#    def send_poweron(self, plugin_id, address):
#        '''
#        Send power on command to a specific plugin.
#        '''    
#        print "poweron"
#        content = {'address': address,
#                   'type': 'poweron'}
#        
#        self._request_id += 1
#        
#        msg = Content(json.dumps(content))
#        msg["delivery mode"] = 1
#        msg['correlation id'] = str(self._request_id)
#        msg['reply to'] = self._qname
#        
#        print "publishing message", msg
#        print "Plugin_id", plugin_id
#
#        self._channel.basic_publish(exchange="houseagent.direct", content=msg, routing_key=plugin_id)
#        
#        # create new deferred
#        d = defer.Deferred()
#        self._outstanding_requests[self._request_id] = d
#        return d
#    
#    def send_thermostat_setpoint(self, plugin_id, address, temperature):
#        '''
#        Send thermostat setpoint command to a device.
#        '''    
#        content = {'address': address,
#                   'type': 'thermostat_setpoint', 
#                   'temperature': temperature}
#        
#        self._request_id += 1
#        
#        msg = Content(json.dumps(content))
#        msg["delivery mode"] = 1
#        msg['correlation id'] = str(self._request_id)
#        msg['reply to'] = self._qname
#
#        self._channel.basic_publish(exchange="houseagent.direct", content=msg, routing_key=plugin_id)
#        
#        # create new deferred
#        d = defer.Deferred()
#        self._outstanding_requests[self._request_id] = d
#        return d
#    
#    def get_plugins_by_type(self, type):
#        '''
#        Get's plugins by type.
#        '''
#        output = []
#        for p in self._plugins:
#
#            if p.type == type:
#                output.append(p)
#        
#        return output
#
#    def send_dimlevel(self, plugin_id, address, level):
#        '''
#        Send dim level for a certain device to a plug-in.
#        @param plugin_id: the plug-in to send the dim command to
#        @param address: the address of the device
#        @param level: the level to dim with
#        '''
#        content = {'address': address,
#                   'type': 'dim',
#                   'level': level}
#        
#        self._request_id += 1
#        
#        msg = Content(json.dumps(content))
#        msg["delivery mode"] = 1
#        msg['correlation id'] = str(self._request_id)
#        msg['reply to'] = self._qname
#
#        self._channel.basic_publish(exchange="houseagent.direct", content=msg, routing_key=plugin_id)
#        
#        # create new deferred
#        d = defer.Deferred()
#        self._outstanding_requests[self._request_id] = d
#        return d    
#    
#    def send_poweroff(self, plugin_id, address):
#        '''
#        Send power off command to a specific plugin.
#        '''    
#        content = {'address': address,
#                   'type': 'poweroff'}
#        
#        self._request_id += 1
#        
#        msg = Content(json.dumps(content))
#        msg["delivery mode"] = 1
#        msg['correlation id'] = str(self._request_id)
#        msg['reply to'] = self._qname
#
#        self._channel.basic_publish(exchange="houseagent.direct", content=msg, routing_key=plugin_id)
#        
#        # create new deferred
#        d = defer.Deferred()
#        self._outstanding_requests[self._request_id] = d
#        return d     
#    
#    @inlineCallbacks
#    def handle_msg(self, msg, queue):
#        '''
#        This function handles messages received from the RabbitMQ broker.
#        '''
#        d = queue.get()
#        d.addCallback(self.handle_msg, queue)
#        d.addErrback(self.handle_err, queue)
#
#        if msg:
#            print "received message:", msg
#            
#            if msg[4] == "value_updates":
#                message = json.loads(msg.content.body)
#                # Message is a value update from a plugin, handle.
#                for key in message["values"]:
#                    value_id = yield self.db.update_or_add_value(key, message["values"][key], 
#                                                self._plugin_id_by_guid(message["plugin_id"]), 
#                                                message["address"], message["time"])
#                                        
#                    # Notify the eventengine
#                    if self._eventengine:
#                        self._eventengine.device_value_changed(value_id, message["values"][key])
#            
#            elif msg[4] == "network":
#                message = json.loads(msg.content.body)
#                for p in self._plugins:
#                    if p.guid == message["id"]:
#                        p.online = True
#                        p.time = time.time()
#                        p.type = message["type"]                    
#
#            elif msg[4] == "houseagent":
#                print "received RPC reply"
#                message = json.loads(msg.content.body)
#                print self._outstanding_requests
#                correlation_id = int(msg.content.properties['correlation id'])
#                d = self._outstanding_requests[correlation_id]
#                d.callback(message)
#                
#    def _plugin_id_by_guid(self, guid):
#        '''
#        This helper function returns a plugin_id based upon a plugin's GUID.
#        '''
#        for p in self._plugins:
#            if p.guid == guid:
#                return p.id
#    
#    def register_eventengine(self, eventengine):
#        self._eventengine = eventengine
#        
#class Plugin(object):
#    '''
#    This is a skeleton class for a network plugin.
#    '''
#    def __init__(self, guid, id, time):
#        self.guid = guid
#        self.id = id
#        self.time = time
#        self.online = False
#        self.type = None
