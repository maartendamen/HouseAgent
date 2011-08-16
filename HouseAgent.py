from houseagent.core.coordinator import Coordinator
from houseagent.core.events import EventHandler
from houseagent.core.web import Web
from twisted.internet import reactor
from twisted.python import log
import sys
import os
import ConfigParser
if os.name == "nt":
    import win32service
    import win32serviceutil
    import win32event
    import win32evtlogutil
       
class MainWrapper():
    '''
    This is the main wrapper for HouseAgent, this class takes care of starting all important
    core components for HouseAgent such as the event engine, network coordinator etc.
    '''    
    def __init__(self):

        from houseagent.utils.generic import get_configurationpath
        self.config_path = get_configurationpath()
        
        if os.path.exists(os.path.join(self.config_path, 'HouseAgent.conf')):
            config = ConfigParser.RawConfigParser()
            config.read(os.path.join(self.config_path, 'HouseAgent.conf'))
            self.port = config.getint('webserver', 'port')
            self.logging = config.getboolean('general', 'logging')
            
            # Get broker information (RabbitMQ)
            self.broker_host = config.get("broker", "host")
            self.broker_port = config.getint("broker", "port")
            self.broker_user = config.get("broker", "username")
            self.broker_pass = config.get("broker", "password")
            self.broker_vhost = config.get("broker", "vhost")
        else:
            print "Configuration file not found! Make sure the configuration file is placed in the proper directory. For *nix: /etc/HouseAgent/, for Windows C:\Programdata\HouseAgent"
            sys.exit()
    
    def start(self):
              
        if self.logging:
            log.startLogging(sys.stdout)
            log.startLogging(open('main.log', 'w'))
        
        log.msg("Starting HouseAgent coordinator...")
        coordinator = Coordinator("houseagent", self.broker_host, self.broker_port, self.broker_user,
                                  self.broker_pass, self.broker_vhost)
        
        log.msg("Starting HouseAgent event handler...")
        event_handler = EventHandler(coordinator)
        
        log.msg("Starting HouseAgent web server...")
        webserver = Web(self.port, coordinator, event_handler)
        webserver.start()
        if os.name == 'nt':
            reactor.run(installSignalHandlers=0)
        else: 
            reactor.run()
        return True    

if os.name == "nt":    
    
    class HouseAgentService(win32serviceutil.ServiceFramework):
        '''
        This class is a Windows Service handler, it's common to run
        long running tasks in the background on a Windows system, as such we
        use Windows services for HouseAgent
        '''        
        _svc_name_ = "hamain"
        _svc_display_name_ = "HouseAgent - Main Service"
        
        def __init__(self,args):
            win32serviceutil.ServiceFramework.__init__(self,args)
            self.hWaitStop=win32event.CreateEvent(None, 0, 0, None)
            self.isAlive=True
    
        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            reactor.stop()
            win32event.SetEvent(self.hWaitStop)
            self.isAlive=False
    
        def SvcDoRun(self):
            import servicemanager
                   
            win32evtlogutil.ReportEvent(self._svc_name_,servicemanager.PYS_SERVICE_STARTED,0,
            servicemanager.EVENTLOG_INFORMATION_TYPE,(self._svc_name_, ''))
    
            self.timeout=1000  # In milliseconds (update every second)
    
            main = MainWrapper()
            
            # Fix working directory, Python Windows service bug
            current_dir = os.path.dirname(sys.executable)
            os.chdir(current_dir)
                        
            if main.start():
                win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE) 
    
            win32evtlogutil.ReportEvent(self._svc_name_,servicemanager.PYS_SERVICE_STOPPED,0,
                                        servicemanager.EVENTLOG_INFORMATION_TYPE,(self._svc_name_, ''))
    
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
    
            return

if __name__ == '__main__':
    
    if os.name == "nt":    
        
        if len(sys.argv) == 1:
            try:
    
                import servicemanager, winerror
                evtsrc_dll = os.path.abspath(servicemanager.__file__)
                servicemanager.PrepareToHostSingle(HouseAgentService)
                servicemanager.Initialize('HouseAgentService', evtsrc_dll)
                servicemanager.StartServiceCtrlDispatcher()
    
            except win32service.error, details:
                if details[0] == winerror.ERROR_FAILED_SERVICE_CONTROLLER_CONNECT:
                    win32serviceutil.usage()
        else:    
            win32serviceutil.HandleCommandLine(HouseAgentService)
    else:
        main = MainWrapper()
        main.start()
