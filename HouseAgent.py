import os
from houseagent.utils.config import Config
from houseagent import config_file
from houseagent.core.coordinator import Coordinator
from houseagent.core.events import EventHandler
from houseagent.core.web import Web
from houseagent.core.database import Database
from houseagent.core.databaseflash import DatabaseFlash
from twisted.internet import reactor
from houseagent.plugins import pluginapi
          
class MainWrapper():
    '''
    This is the main wrapper for HouseAgent, this class takes care of starting all important
    core components for HouseAgent such as the event engine, network coordinator etc.
    '''
    def start(self):     
     
        self.log = pluginapi.Logging("Main")
        self.log.set_level(config.general.loglevel)
        
        self.log.debug("Starting HouseAgent database layer...")
        if config.embedded.enabled:
            database = DatabaseFlash(self.log, config.general.dbfile, config.embedded.db_save_interval)
        else:
            database = Database(self.log, config.general.dbfile)
        
        self.log.debug("Starting HouseAgent coordinator...")
        coordinator = Coordinator(self.log, database)

        coordinator.init_broker(config.zmq.broker_host, config.zmq.broker_port)
        
        self.log.debug("Starting HouseAgent event handler...")
        event_handler = EventHandler(coordinator, database)
        
        self.log.debug("Starting HouseAgent web server...")
        Web(self.log, config.webserver.host, config.webserver.port,\
            config.webserver.backlog, coordinator, event_handler, database)
        
        if os.name == 'nt':
            reactor.run(installSignalHandlers=0)
        else: 
            reactor.run()
        return True

if os.name == "nt": 
    class MainService(pluginapi.WindowsService):
        '''
        This is the main service definition for HouseAgent.
        It takes care of running HouseAgent as Windows Service.
        '''
        _svc_name_ = "hamain" 
        _svc_display_name_ = "HouseAgent - Main Service"
        
        def start(self):
            main = MainWrapper()
            main.start()

if __name__ == '__main__':

    config = Config(config_file)

    if os.name == "nt":
        if config.general.runasservice:
            pluginapi.handle_windowsservice(MainService) # We want to start as a Windows service on Windows.
        else:
            main = MainWrapper()
            main.start() 
    else:
        main = MainWrapper()
        main.start()
