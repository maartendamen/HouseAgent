import os
import logging, logging.handlers
import sys
import json
import time
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
from twisted.internet import reactor, task
from houseagent import log_path
from txZMQ import ZmqFactory, ZmqEndpoint, ZmqPubConnection, ZmqEndpointType
from txZMQ.xreq_xrep import ZmqXREPConnection

class PluginAPI(object):
    '''
    This is the PluginAPI for HouseAgent.
    ''' 
    def __init__(self, guid, plugintype=None, collector_host='127.0.0.1', collector_port='13001', rpc_host=None, 
                 rpc_port=None, **callbacks):
        
        self.factory = ZmqFactory()
        self.guid = guid
        self.plugintype = plugintype
        
        # Set-up connections
        self.collector_connection(collector_host, collector_port)
        self.rpc_connection(rpc_host, rpc_port)
                
        # Handle callbacks
        self.custom_callback = None
        self.poweron_callback = None
        self.poweroff_callback = None
        self.dim_callback = None
        self.thermostat_setpoint_callback = None
        self.crud_callback = None
        
        for callback in callbacks:
            if callback == "crud":
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
        l = task.LoopingCall(self.ping)
        l.start(10.0)
    
    def collector_connection(self, host, port):
        '''
        This function sets up a connection to the HouseAgent collector.
        @param host: the host of the collector
        @param port: the port of the collector
        '''
        endpoint = ZmqEndpoint(ZmqEndpointType.Connect, 'tcp://%s:%s' % (host, port))
        self.publish_socket = ZmqPubConnection(self.factory, endpoint)
        
    def rpc_connection(self, host, port):
        '''
        This function creates a new RPC connection for the plugin.
        @param host: the destination host to connect to
        @param port: the destination port to connect to
        '''
        self.rpc_socket = ZmqXREPConnection(self.factory, ZmqEndpoint(ZmqEndpointType.Connect, 'tcp://%s:%s' % (host, port)))
        self.rpc_socket.gotMessage = self.handle_rpc_message
        
    def handle_rpc_message(self, message_id, *msg):
        '''
        This handles a RPC message.
        @param message_id: the id associated with the message.
        '''
        try:
            tag = msg[0]
            message = json.loads(msg[1])
        except:
            return       

        if tag == 'custom':
            if self.custom_callback:
                self.call_callback(self.custom_callback, message_id, message['action'], message['parameters'])
        elif tag == 'power_on':
            if self.poweron_callback:
                self.call_callback(self.poweron_callback, message_id, message['address'])
        elif tag == 'power_off':
            if self.poweroff_callback:
                self.call_callback(self.poweroff_callback, message_id, message['address'])
        elif tag == 'dim':
            if self.dim_callback:
                self.call_callback(self.dim_callback, message_id, message['address'], message['level'])
        elif tag == 'thermostat_setpoint':
            if self.thermostat_setpoint_callback:
                self.call_callback(self.thermostat_setpoint_callback, message_id, message['address'], message['temperature'])
        elif tag == 'crud':
            if self.crud_callback:
                self.call_callback(self.crud_callback, message_id, message['action'], message['parameters'])

    def call_callback(self, function, message_id, *args):
        '''
        This function calls a callback function in the plugin.
        @param function: the function to call
        @param message_id: the message id associated with the RPC request
        '''
        def cb_reply(result):
            self.rpc_socket.reply(message_id, json.dumps(result))
            
        def cb_failure(result):
            self.rpc_socket.reply(message_id, json.dumps(result))
        
        # Do the actual callback in the plugin
        try:
            function(*args).addCallbacks(cb_reply, cb_failure)
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
        
        self.publish_socket.publish(json.dumps(content), 'value_update')

    def ping(self):
        '''
        This function sends a keep alive message to the coordinator.
        '''
        content = {"id": self.guid,
                   "type": self.plugintype}

        self.publish_socket.publish(json.dumps(content), 'network')
                         
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
        
        # Regular Python logging module
        self.logger = logging.getLogger()
        log_handler = logging.handlers.RotatingFileHandler(filename = os.path.join(log_path, "%s.log" % name), 
                                                       maxBytes = maxkbytes * 1024,
                                                       backupCount = count)
        
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        
        if console:
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
        This function allows you to log a plugin warning message.
        @param message: the message to log.
        '''
        twisted_log.msg(message, logLevel=logging.INFO)
    
    def debug(self, message):
        '''
        This function allows you to log a plugin debug message.
        @param message: the message to log.
        '''        
        twisted_log.msg(message, logLevel=logging.DEBUG)

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
