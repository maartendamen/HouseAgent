import os
import logging 
import logging.handlers
import sys
import json
import time
from houseagent.utils.config import Config
if os.name == "nt":
    import win32serviceutil
    import win32event
    import win32service
    import win32evtlogutil
    from twisted.internet import win32eventreactor
    try:
        win32eventreactor.install()
    except:
        pass        
from twisted.python import log as twisted_log
from twisted.internet import reactor, task, defer
from txZMQ import ZmqFactory, ZmqEndpoint, ZmqConnection, ZmqEndpointType
from zmq.core import constants
from houseagent import config_file

class PluginConnection(ZmqConnection):        
    '''
    Class that takes care of connecting to the broker.
    '''
    socketType = constants.XREQ
        
    def __init__(self, factory, pluginapi, *endpoints):
        '''
        Initialize a new PluginConnection instance.
        
        @param factory: an instance of ZmqFactory
        @param pluginapi: an instance of PluginAPI
        '''
        ZmqConnection.__init__(self, factory, *endpoints)
        self.pluginapi = pluginapi
        self.factory = factory
        self.endpoints = endpoints
    
    def send_msg(self, *message_parts):
        '''
        Send a message to the broker.
        
        @param message_parts: the message parts to send. 
        '''
        d = defer.Deferred()
        message = ['']
        message.extend(message_parts)
        self.send(message)
        return d
    
    def messageReceived(self, msg):
        '''
        Function called when a message has been received.
        @param msg: the message that has been received
        '''     
        if msg[1] == '\x01':
            # Handle ready request
            if self.pluginapi.isready:
                self.pluginapi.ready()
        
        elif msg[1] == '\x04':
            # Handle RPC reply
            self.pluginapi.handle_rpc_message(msg[2], msg[3])
            
        elif msg[1] == '\x06':

            # Handle CRUD callback
            if self.pluginapi.crud_callback:
                message = json.loads(msg[2])
                self.pluginapi.crud_callback(message['type'], message['action'], message['parameters'])

class PluginAPI(object):
    '''
    This is the PluginAPI for HouseAgent.
    ''' 
    
    def __init__(self, guid, plugintype=None, broker_host='127.0.0.1', broker_port='13001', **callbacks):
        '''
        Initialize a new PluginAPI instance.
        
        @param guid: the guid of the plugin
        @param plugintype: the type of the plugin
        @param broker_host: the broker host
        @param broker_port: the broker port
        '''
        
        self.factory = ZmqFactory()
        self.guid = guid
        self.plugintype = plugintype
        self.isready = False
        
        # Set-up connection
        self.connection = PluginConnection(self.factory, self, ZmqEndpoint(ZmqEndpointType.Connect, 
                                                                     'tcp://%s:%s' % (broker_host, broker_port)))
                
        # Handle callbacks
        self.custom_callback = None
        self.poweron_callback = None
        self.poweroff_callback = None
        self.dim_callback = None
        self.thermostat_setpoint_callback = None
        self.crud_callback = None
        
        self.callbacks = []
        
        for callback in callbacks:
            if callback == "crud":
                self.callbacks.append('crud')
                self.crud_callback = callbacks[callback]
            elif callback == 'poweron':
                self.poweron_callback = callbacks[callback]
            elif callback == 'poweroff':
                self.poweroff_callback = callbacks[callback]
            elif callback == 'custom':
                self.custom_callback = callbacks[callback]
            elif callback == 'thermostat_setpoint':
                self.thermostat_setpoint_callback = callbacks[callback]
            elif callback == 'dim':
                self.dim_callback = callbacks[callback]
                
        # Start keep alive
        l = task.LoopingCall(self.heartbeat)
        l.start(30.0)
        
    def handle_rpc_message(self, message_id, message):
        '''
        This handles a RPC message.
        @param message_id: the id associated with the message.
        '''

        message = json.loads(message)  

        if message['type'] == 'custom':
            if self.custom_callback:
                self.call_callback(self.custom_callback, message_id, message['action'], message['parameters'])
        elif message['type'] == 'poweron':
            if self.poweron_callback:
                self.call_callback(self.poweron_callback, message_id, message['address'])
        elif message['type'] == 'poweroff':
            if self.poweroff_callback:
                self.call_callback(self.poweroff_callback, message_id, message['address'])
        elif message['type'] == 'dim':
            if self.dim_callback:
                self.call_callback(self.dim_callback, message_id, message['address'], message['level'])
        elif message['type'] == 'thermostat_setpoint':
            if self.thermostat_setpoint_callback:
                self.call_callback(self.thermostat_setpoint_callback, message_id, message['address'], message['temperature'])

    def call_callback(self, function, message_id, *args):
        '''
        This function calls a callback function in the plugin.
        @param function: the function to call
        @param message_id: the message id associated with the RPC request
        '''
        def cb_reply(result):
            message = [b'', chr(5), message_id, json.dumps(result)]
            print "Sending: %r" % (message)
            self.connection.send(message)
        
        # Do the actual callback in the plugin
        try:
            function(*args).addCallbacks(cb_reply, cb_reply)
        except Exception as e:
            print "Failed to do callback, fix the plugin function: %s" % (e)

    def value_update(self, address, values):
        '''
        This function is called by a plugin when a value has been updated.
        The message is published to the collector.
        @param address: the address of the device
        @param values: one or multiple values to be updated
        '''
        content = {"address": address,
                   "values": values, 
                   "time": time.time(),
                   'plugin_id': self.guid}
    
        self.connection.send_msg(chr(3), json.dumps(content))

    def heartbeat(self):
        '''
        This function sends a keep alive (heartbeat) message to the coordinator.
        '''
        if self.isready:
            self.connection.send_msg(chr(2))
        
    def ready(self):
        '''
        Set the plugin to the ready state.
        Send a message on the broker about our state.
        '''
        self.isready = True
        self.connection.send_msg(chr(1), self.guid, self.plugintype, json.dumps(self.callbacks))
                         
class Logging():
    '''
    This class provides generic logging facilities for HouseAgent plug-ins. 
    '''
    
    def __init__(self, name, maxkbytes=1024, count=5, console=True):
        '''
        Using this class you can add logging to your plug-in.
        It provides a generic way of storing logging information.
        
        @param name: the name of the logfile 
        @param maxkbytes: the maximum logfile size in kilobytes 
        @param count: the maximum number of logfiles to keep for rotation
        @param console: specifies whether or not to log to the console, this defaults to "True"
        '''
        
        # Start Twisted python log observer
        observer = twisted_log.PythonLoggingObserver()
        observer.start()
        
        # Get logpath
        config = Config(config_file)
        
        # Regular Python logging module
        self.logger = logging.getLogger()
        log_handler = logging.handlers.RotatingFileHandler(filename = os.path.join(config.general.logpath, "%s.log" % name), maxBytes = config.general.logsize * 1024, backupCount = config.general.logcount)
        
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        
        if config.general.logconsole:
            console_handler = logging.StreamHandler(sys.stdout) 
            console_handler.setFormatter(formatter)
        
        log_handler.setFormatter(formatter)
        
        self.logger.addHandler(log_handler)
        self.logger.addHandler(console_handler)
        
    def set_level(self, level):        
        '''
        This function allows you to set the level of logging.
        By default everything will be logged. 
        @param level: the level of logging, valid arguments are debug, warning or error.
        '''
        if level == 'debug':
            self.logger.setLevel(logging.DEBUG)
        elif level == 'warning':
            self.logger.setLevel(logging.WARNING)
        elif level == 'error':
            self.logger.setLevel(logging.ERROR)
        elif level == 'critical':
            self.logger.setLevel(logging.CRITICAL)
        elif level == 'info':
            self.logger.setLevel(logging.INFO)
        elif level == 'none':
            self.logger.setLevel(logging.NOTSET)
            
    def error(self, message):
        '''
        This function allows you to log a plugin error message.
        @param message: the message to log.
        '''
        twisted_log.msg(message, logLevel=logging.ERROR)
        
    def warning(self, message):
        '''
        This function allows you to log a plugin warning message.
        @param message: the message to log.
        '''
        twisted_log.msg(message, logLevel=logging.WARNING)

    def info(self, message):
        '''
        This function allows you to log a plugin info message.
        @param message: the message to log.
        '''
        twisted_log.msg(message, logLevel=logging.INFO)
    
    def debug(self, message):
        '''
        This function allows you to log a plugin debug message.
        @param message: the message to log.
        '''        
        twisted_log.msg(message, logLevel=logging.DEBUG)
    def critical(self, message):
        '''
        This function allows you to log a plugin critical message.
        @param message: the message to log.
        '''        
        twisted_log.msg(message, logLevel=logging.CRITICAL)

if os.name == "nt":        
    class WindowsService(win32serviceutil.ServiceFramework):
        '''
        This class is a Windows Service handler, it's common to run
        long running tasks in the background on a Windows system, as such we
        use Windows services for HouseAgent.
        
        Plugins can ovveride this class in order to provide a Windows service interface for their plugins.
        '''        
        _svc_name_ = "not set"
        _svc_display_name_ = "not set"
        
        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self,args)
            self.hWaitStop=win32event.CreateEvent(None, 0, 0, None)
            self.isAlive=True
    
        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            reactor.stop()
            win32event.SetEvent(self.hWaitStop)
            self.isAlive=False
    
        def start(self):
            pass
    
        def SvcDoRun(self):
            import servicemanager
                   
            win32evtlogutil.ReportEvent(self._svc_name_,servicemanager.PYS_SERVICE_STARTED,0,
            servicemanager.EVENTLOG_INFORMATION_TYPE,(self._svc_name_, ''))
    
            self.timeout=1000  # In milliseconds (update every second)
            self.start()
    
            # Fix working directory, Python Windows service bug
            current_dir = os.path.dirname(sys.executable)
            os.chdir(current_dir)
    
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE) 
    
            win32evtlogutil.ReportEvent(self._svc_name_,servicemanager.PYS_SERVICE_STOPPED,0,
                                        servicemanager.EVENTLOG_INFORMATION_TYPE,(self._svc_name_, ''))
    
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
    
            return
        
    def handle_windowsservice(serviceclass):
        '''
        This function handles a Windows service class.
        It displays the appropriate command line help, and validaes command line arguements.
        @param serviceclass: a reference to a overridden WindowsService class.
        '''
        if len(sys.argv) == 1:
            try:
                import servicemanager, winerror
                evtsrc_dll = os.path.abspath(servicemanager.__file__)
                servicemanager.PrepareToHostSingle(serviceclass)
                servicemanager.Initialize(serviceclass.__name__, evtsrc_dll)
                servicemanager.StartServiceCtrlDispatcher()
    
            except win32service.error, details:
                if details[0] == winerror.ERROR_FAILED_SERVICE_CONTROLLER_CONNECT:
                    win32serviceutil.usage()
        else:    
            win32serviceutil.HandleCommandLine(serviceclass)
