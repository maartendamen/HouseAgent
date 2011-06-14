from twisted.internet import reactor
from twisted.internet.protocol import ClientCreator
from txamqp.queue import Closed
from txamqp.protocol import AMQClient
from txamqp.client import TwistedDelegate
import txamqp.spec, os, inspect, json, time
from txamqp.content import Content
from twisted.internet import task
from twisted.internet.defer import inlineCallbacks
from twisted.internet.error import ConnectionRefusedError, ConnectionLost
from twisted.python import log

class PluginAPI(object):
    '''
    This is the PluginAPI for HouseAgent, it allows you to create a connection to the broker.
    ''' 
    def __init__(self, plugin_id=None, plugin_type=None, broker_ip='127.0.0.1', broker_port=5672, username='guest', password='guest', vhost='/', logging=False):

        self._broker_host = broker_ip
        self._broker_port = broker_port
        self._broker_user = username
        self._broker_pass = password
        self._broker_vhost = vhost

        self._qname = plugin_id
        self._plugintype = plugin_type
        self._tag = 'mq%d' % id(self)
        
        self._logging = True

        self._connect_client()

    @inlineCallbacks
    def _connect_client(self):
        '''
        Sets up a client connection to the RabbitMQ broker.
        '''        
        spec = txamqp.spec.load("../../specs/amqp0-8.xml")
        try:
            client = yield ClientCreator(reactor, AMQClient, TwistedDelegate(), self._broker_vhost, spec).connectTCP(self._broker_host, int(self._broker_port))
        except ConnectionRefusedError:            
            self._log("Failed to connect to RabbitMQ broker.. retrying..")
            reactor.callLater(10.0, self._connect_client)
            return
        except Exception, e:
            self._log("Unhandled exception while connecting to RabbitMQ broker: %s" % e)
          
        self._log("Connected to RabbitMQ broker, authenticating...")
        yield client.authenticate(self._broker_user, self._broker_pass)
        self._setup(client)
    
    @inlineCallbacks
    def _setup(self, client):
        self._client = client
        
        try:
            self._channel = yield self._client.channel(1)
        except:
            self._log("Error setting up RabbitMQ communication channel!")      

        try:
            yield self._channel.channel_open()
        except:
            self._log("Error opening RabbitMQ communication channel!")
                        
        # Declare exchange
        try:
            yield self._channel.exchange_declare(exchange="houseagent.direct", type="direct", durable="True")
        except:
            self._log("Error declaring RabbitMQ exchange!")

        # Declare queue
        try:
            yield self._channel.queue_declare(queue=self._qname, durable=True, auto_delete=True)
        except:
            self._log("Error declaring RabbitMQ queue!")

        # Bind queue
        try:
            yield self._channel.queue_bind(queue=self._qname, exchange="houseagent.direct",
                                     routing_key=self._qname)
        except:
            self._log("Error binding RabbitMQ queue's!")

        # Set-up consumer
        try:
            self._channel.basic_consume(queue=self._qname, no_ack=True,
                                        consumer_tag=self._tag)
        except:
            self._log("Error setting up RabbitMQ consumer!")

        # Start receiving message from the broker
        self._log("Succesfully setup RabbitMQ broker connection...")
        self._client.queue(self._tag).addCallback(lambda queue: self.handle_msg(None, queue))                    
        
        # This checks all plugins every 10 seconds
        l = task.LoopingCall(self._ping)
        l.start(10.0)
    
    def handle_err(self, failure, queue):
        '''
        This handles message get errors. 
        '''
        if failure.check(Closed):
            self._connect_client()
        else:
            print 'error: %s' % failure
            self.handle_msg(None, queue)

    def setup_error(self, failure):
        print 'ERROR: failed to create RPC Receiver: %s' % failure

    def _log(self, msg):
        '''
        This logs a message to the HouseAgent log.
        '''
        if self._logging:
            log.msg(msg)
    
    def handle_msg(self, msg, queue):
        d = queue.get()
        d.addCallback(self.handle_msg, queue)
        d.addErrback(self.handle_err, queue)

        if msg:
            print "received message", msg
            replyq = msg.content.properties.get('reply to',None)
            
            if msg.content and replyq:
                request = json.loads(msg.content.body)
                
                print "received custom request", request
                
                if request["type"] == "custom":
                    result = self.customcallback.on_custom(request["action"], request["parameters"])
                    
                    content = Content(json.dumps(result))
                    content.properties['correlation id'] = msg.content.properties['correlation id']
                    self._channel.basic_publish(exchange="", content=content, routing_key="houseagent")
                elif request["type"] == "poweron":
                    print "POWERON"
                    result = self.poweroncallback.on_poweron(request["address"])
                    
                    content = Content(json.dumps(result))
                    content.properties['correlation id'] = msg.content.properties['correlation id']
                    self._channel.basic_publish(exchange="", content=content, routing_key="houseagent")      
                elif request["type"] == "poweroff":
                    result = self.poweroncallback.on_poweroff(request["address"])
                    
                    content = Content(json.dumps(result))
                    content.properties['correlation id'] = msg.content.properties['correlation id']
                    self._channel.basic_publish(exchange="", content=content, routing_key="houseagent")         
                elif request["type"] == "thermostat_setpoint":
                    result = self.thermostatcallback.on_thermostat_setpoint(request['address'], request['temperature'])
                    
                    content = Content(json.dumps(result))
                    content.properties['correlation id'] = msg.content.properties['correlation id']
                    self._channel.basic_publish(exchange="", content=content, routing_key="houseagent")         
                
    def register_custom(self, calling_class):
        """
        Register's for a custom command callback.
        """
        self.customcallback = calling_class
        
    def register_poweron(self, calling_class):
        self.poweroncallback = calling_class
        
    def register_poweroff(self, calling_class):
        self.poweroffcallback = calling_class
        
    def register_thermostat_setpoint(self, calling_class):
        self.thermostatcallback = calling_class
            
    def valueUpdate(self, address, values):
        """
        Called by a plugin when a device value has been updated.
        """
        content = {"address": address,
                   "values": values, 
                   "time": time.time(),
                   "plugin_id": self._qname}
        
        msg = Content(json.dumps(content))
        msg["delivery mode"] = 2
        self._channel.basic_publish(exchange="houseagent.direct", content=msg, routing_key="value_updates")
        print "Sending message: %s" % content
        
    def _ping(self):
        '''
        Sends an alive message on the network.
        '''
        content = {"id": self._qname,
                   "type": self._plugintype}
        
        msg = Content(json.dumps(content))
        msg["delivery mode"] = 1
        self._channel.basic_publish(exchange="houseagent.direct", content=msg, routing_key="network")