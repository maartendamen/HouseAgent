from pyrrd.rrd import RRD, RRA, DS
from twisted.enterprise.adbapi import ConnectionPool
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks, returnValue
import datetime
import time
import os.path, sys
import shutil

class Database():
    """
    HouseAgent database interaction.
    """
    def __init__(self, log, db_location):
        self.log = log

        type = "sqlite"

        self.coordinator = None

        # Note: cp_max=1 is required otherwise undefined behaviour could occur when using yield icw subsequent
        # runQuery or runOperation statements
        if type == "sqlite":
            self.dbpool = ConnectionPool("sqlite3", db_location, check_same_thread=False, cp_max=1)
       
        # Check database schema version and upgrade when required
        self.updatedb('0.1')
             
    def updatedb(self, dbversion):
        '''
        Perform a database schema update when required. 
        '''
        # Note: runInteraction runs all queries defined within the specified function as part of a transaction.
        return self.dbpool.runInteraction(self._updatedb, dbversion)

    def _updatedb(self, txn, dbversion):
        '''
        Check whether a database schema update is required and act accordingly.
        '''
        # Note: Although all queries are run as part of a transaction, a create or drop table statement result in an implicit commit

        # Query the version of the current schema
        try:
            result = txn.execute("SELECT parm_value FROM common WHERE parm = 'schema_version'").fetchall()
        except:
            result = None
            
        if result:
            version = result[0][0]
        else:
            version = '0.0'

        if float(version) > float(dbversion):
            self.log.error("ERROR: The current database schema (%s) is not supported by this version of HouseAgent" % version)
            # Exit HouseAgent
            sys.exit()
        
        elif float(version) == float(dbversion):
            self.log.debug("Database schema is up to date")
            return
        
        else:
            self.log.info("Database schema will be updated from %s to %s:" % (version, dbversion))

            # Before we start manipulating the database schema, first make a backup copy of the database
            try:
                shutil.copy(db_location, db_location + datetime.datetime.strftime(datetime.datetime.now(), ".%y%m%d-%H%M%S"))
            except:
                self.log.error("Cannot make a backup copy of the database (%s)", sys.exc_info()[1])
                return

            if version == '0.0':
                try:
                    # Create common table
                    txn.execute("CREATE TABLE IF NOT EXISTS common (parm VARCHAR(16) PRIMARY KEY, parm_value VARCHAR(24) NOT NULL)")
            
                    # Add schema version to database
                    txn.execute("INSERT INTO common (parm, parm_value) VALUES ('schema_version', ?)", [dbversion])

                    # Set primary key of the devices table on address + plugin_id to prevent adding duplicate devices
                    txn.execute("CREATE TEMPORARY TABLE devices_backup(id INTEGER PRIMARY KEY, name VARCHAR(45), address VARCHAR(45) NOT NULL, plugin_id INTEGER NOT NULL, location_id INTEGER)")
                    txn.execute("INSERT INTO devices_backup SELECT id, name, address, plugin_id, location_id FROM devices")
                    txn.execute("DROP TABLE devices")
                    txn.execute("CREATE TABLE devices(id INTEGER PRIMARY KEY, name VARCHAR(45), address VARCHAR(45) NOT NULL, plugin_id INTEGER, location_id INTEGER)")
                    txn.execute("CREATE UNIQUE INDEX device_address ON devices (address, plugin_id)")
                    txn.execute("INSERT INTO devices SELECT id, name, address, plugin_id, location_id FROM devices_backup")
                    txn.execute("DROP TABLE devices_backup")

                    self.log.info("Successfully upgraded database schema")
                except:
                    self.log.error("Database schema upgrade failed (%s)" % sys.exc_info()[1])

    def query_plugin_auth(self, authcode):
        return self.dbpool.runQuery("SELECT authcode, id from plugins WHERE authcode = '%s'" % authcode)

    def check_plugin_auth(self, result):
        if len(result) >= 1:
            return {'registered': True}
        else:
            return {'registered': False}

    def insert_result(self, result):
        return {'received': True}

    def add_event(self, name, enabled, triggers):
        """
        This function adds an event to the database.
        """
        d = self.dbpool.runQuery("INSERT INTO events (name, enabled) VALUES (?, ?)", (name, enabled) )
        def event_added(result):
            print "added event"
            return self.dbpool.runQuery("select id from events order by id desc limit 1")      
        
        d.addCallback(event_added)
        def got_id(result):
            event_id = result[0][0]
            
            print "got event_id", result[0][0]
            print "triggers=",triggers
            
            # Add triggers
            deferredlist = []
            
            for trigger in triggers:
                trigger_type_id = trigger["trigger_type"]
                print "trigger", trigger
                
                def got_triggerid(result):
                    trigger_id = result[0][0]
                    
                    print "parameters", trigger["parameters"]
                    for name, value in trigger["parameters"].iteritems():
                        print name, value
                        deferredlist.append(self.dbpool.runQuery("INSERT INTO trigger_parameters (name, value, " +
                                                                 "triggers_id) VALUES (?, ?, ?)", (name, value, trigger_id)))
                
                def trigger_added(result):
                    self.dbpool.runQuery("select id from triggers order by id desc limit 1").addCallback(got_triggerid)     
                
                # Triggers
                deferredlist.append(self.dbpool.runQuery("INSERT INTO triggers (trigger_types_id, events_id)" +
                                                         " VALUES (?, ?)", (trigger_type_id, event_id)).addCallback(trigger_added) )        
                    
            d = defer.gatherResults(deferredlist)
            return d
            
        d.addCallback(got_id)
        
        def added_triggers(result):
            print "triggers added"
            
        d.addCallback(added_triggers)
        return d
    
    def add_location(self, name, parent):
        if parent:
            return self.dbpool.runQuery("INSERT INTO locations (name, parent) VALUES (?, ?)", [name, parent])
        else:
            return self.dbpool.runQuery("INSERT INTO locations (name) VALUES (?)", [name])
    
    @inlineCallbacks
    def add_event2(self, name, enabled, conditions, actions, trigger):
        '''
        This adds an event to the database.
        '''
        # Add event, and get event id
        yield self.dbpool.runQuery("INSERT INTO events (name, enabled) VALUES (?, ?)", [name, enabled])
        eventid = yield self.dbpool.runQuery("select id from events order by id desc limit 1")
        eventid = eventid[0][0]
        
        # Add conditions
        for condition in conditions:
            condition_type_id = condition["condition_type"]
            
            yield self.dbpool.runQuery("INSERT INTO conditions (condition_types_id, events_id)" +
                                       " VALUES (?, ?)", [condition_type_id, eventid])
            
            condition_id = yield self.dbpool.runQuery("select id from conditions order by id desc limit 1")
            condition_id = condition_id[0][0]
            
            for name, value in condition["parameters"].iteritems():
                yield self.dbpool.runQuery("INSERT INTO condition_parameters (name, value, " +
                                           "conditions_id) VALUES (?, ?, ?)", [name, value, condition_id])
        
        # Add actions
        for action in actions:
            action_type_id = action["action_type"]
            
            yield self.dbpool.runQuery("INSERT INTO actions (action_types_id, events_id)" +
                                       " VALUES (?, ?)", [action_type_id, eventid])
            
            action_id = yield self.dbpool.runQuery("select id from actions order by id desc limit 1")
            action_id = action_id[0][0]
            
            for name, value in action["parameters"].iteritems():
                yield self.dbpool.runQuery("INSERT INTO action_parameters (name, value, " +
                                           "actions_id) VALUES (?, ?, ?)", [name, value, action_id])
                
            
        # Insert trigger
        yield self.dbpool.runQuery("INSERT INTO triggers (trigger_types_id, events_id, conditions)" +
                                   " VALUES (?,?,?)", [trigger["trigger_type"], eventid, trigger["conditions"]])
 
        trigger_id = yield self.dbpool.runQuery("select id from triggers order by id desc limit 1")
        trigger_id = trigger_id[0][0]
       
        for name, value in trigger["parameters"].iteritems():
            yield self.dbpool.runQuery("INSERT INTO trigger_parameters (name, value, " +
                                       "triggers_id) VALUES (?, ?, ?)", [name, value, trigger_id])
               
    
    def add_trigger(self, trigger_type_id, event_id, value_id, parameters):
        print "INSERT INTO triggers (trigger_types_id, events_id, current_values_id) VALUES (%d, %d, %d)" % (int(trigger_type_id),
                                                                                                                                  int(event_id),
                                                                                                                                  int(value_id))
        d = self.dbpool.runQuery("INSERT INTO triggers (trigger_types_id, events_id" + 
                                 ", current_values_id) VALUES (%s, %s, %s)", (int(trigger_type_id),
                                                                              int(event_id),
                                                                              int(value_id)) ) 
        for name, value in parameters.iteritems():
            self.dbpool.runQuery("INSERT INTO trigger_parameters (name, value, triggers_id) VALUES (%s, %s, last_insert_id())", (name, value) )
    
        return d
    
    #def add_action(self, action_type_id, event_id):
    
    def query_latest_device_id(self):
        '''
        This function queries the latest device id.
        '''
        return self.dbpool.runQuery('select id from devices LIMIT 1')
         
    def query_triggers(self):
        return self.dbpool.runQuery("SELECT triggers.id, trigger_types.name, triggers.events_id, triggers.conditions " + 
                                    "FROM triggers INNER JOIN trigger_types ON (triggers.trigger_types_id = trigger_types.id)")

    def query_trigger(self, event_id):
        return self.dbpool.runQuery("SELECT triggers.id, trigger_types.name, triggers.events_id, triggers.conditions " + 
                                    "FROM triggers INNER JOIN trigger_types ON (triggers.trigger_types_id = trigger_types.id) " +
                                    "WHERE triggers.events_id = ? LIMIT 1", [event_id])
        
    def query_conditions(self):
        return self.dbpool.runQuery("SELECT conditions.id, condition_types.name, conditions.events_id " + 
                                    "FROM conditions INNER JOIN condition_types ON (conditions.condition_types_id = condition_types.id)")

    def query_actions(self):
        return self.dbpool.runQuery("SELECT actions.id, action_types.name, actions.events_id " + 
                                    "FROM actions INNER JOIN action_types ON (actions.action_types_id = action_types.id)")

    def query_trigger_parameters(self, trigger_id):
        return self.dbpool.runQuery("SELECT name, value from trigger_parameters WHERE triggers_id = ?", [trigger_id])
    
    def query_condition_parameters(self, condition_id):
        return self.dbpool.runQuery("SELECT name, value from condition_parameters WHERE conditions_id = ?", [condition_id])        

    def query_action_parameters(self, action_id):
        return self.dbpool.runQuery("SELECT name, value from action_parameters WHERE actions_id = ?", [action_id])
    
    def query_device_routing_by_id(self, device_id):
        return self.dbpool.runQuery("SELECT devices.address, plugins.authcode FROM devices " +  
                                    "INNER JOIN plugins ON (devices.plugin_id = plugins.id) "
                                    "WHERE devices.id = ?", [device_id])

    def query_value_properties(self, value_id):
        return self.dbpool.runQuery("SELECT current_values.name, devices.address, devices.plugin_id from current_values " + 
                                    "INNER JOIN devices ON (current_values.device_id = devices.id) " + 
                                    "WHERE current_values.id = ?", [value_id])

    def query_plugin_devices(self, plugin_id):
        return self.dbpool.runQuery("SELECT devices.id, devices.name, devices.address, locations.name from devices " +
                                    "LEFT OUTER JOIN locations ON (devices.location_id = locations.id) " +
                                    "WHERE plugin_id=? ", [plugin_id])

    @inlineCallbacks
    def update_or_add_value(self, name, value, pluginid, address, time=None):
        '''
        This function updates or adds values to the HouseAgent database.
        @param name: the name of the value
        @param value: the actual value of the value
        @param pluginid: the plugin which holds the device information
        @param address: the address of the device being handled
        @param time: the time at which the update has been received, this defaults to now()
        '''
        if not time:
            updatetime = datetime.datetime.now().isoformat(' ').split('.')[0]
        else:
            updatetime = datetime.datetime.fromtimestamp(time).isoformat(' ').split('.')[0]
        
        # Query device first
        device_id = yield self.dbpool.runQuery('select id from devices WHERE plugin_id = ? and address = ? LIMIT 1', (pluginid, address) )

        try:
            device_id = device_id[0][0]
        except:
            returnValue('') # device does not exist
        
        current_value = yield self.dbpool.runQuery("select id, name, history from current_values where name=? AND device_id=? LIMIT 1", (name, device_id))
    
        try:
            value_id = current_value[0][0]
        except:
            value_id = None
    
        if value_id:
            value_id = current_value[0][0]
            
            if current_value[0][2] not in (0, None):
                DataHistory("data", current_value[0][0], value, "GAUGE", 60, int(time))
                
            yield self.dbpool.runQuery("UPDATE current_values SET value=?, lastupdate=? WHERE id=?", (value, updatetime, value_id))
        else:
            yield self.dbpool.runQuery("INSERT INTO current_values (name, value, device_id, lastupdate) VALUES (?, ?, (select id from devices where address=? AND plugin_id=?),  ?)", (name, value, address, pluginid, updatetime))
            current_value = yield self.dbpool.runQuery("select id from current_values where name=? AND device_id=?", (name, device_id))
            value_id = current_value[0][0]
                        
        returnValue(value_id)

    def register_plugin(self, name, uuid, location):
        return self.dbpool.runQuery("INSERT INTO plugins (name, authcode, location_id) VALUES (?, ?, ?)", [str(name), str(uuid), location])

    def query_plugins(self):
        return self.dbpool.runQuery("SELECT plugins.name, plugins.authcode, plugins.id, locations.name, plugins.location_id from plugins " +
                                    "LEFT OUTER JOIN locations ON (plugins.location_id = locations.id)")
    
    def query_plugin_by_type_name(self, type_name):
        return self.dbpool.runQuery("SELECT plugins.id, plugins.authcode from plugins " +
                                    "INNER JOIN plugin_types ON (plugins.plugin_type_id = plugin_types.id)" +
                                    "WHERE plugin_types.name = ? LIMIT 1", [type_name])

    def query_device_classes(self):
        return self.dbpool.runQuery("SELECT * from device_class order by name ASC")
    
    def query_device_types(self):
        return self.dbpool.runQuery("SELECT * from device_types order by name ASC")
       
    @inlineCallbacks
    def cb_device_crud(self, result, action, id=None, plugin=None, address=None, name=None, location=None):
        '''
        Callback function that get's called when a device has been created, updated or deleted in, to or from the database.
        @param result: the result of the action
        @param action: the action initiating the callback being create, update or delete
        @param plugin: the uuid of the plugin owning the device
        @param address: the address of the device
        @param name: the name of the device
        @param location: the name of the location associated with the device
        '''
        if action == "create":
            parms = yield self.dbpool.runQuery("SELECT plugins.authcode, devices.address, devices.name, locations.name FROM devices, plugins, locations WHERE devices.plugin_id = plugins.id AND devices.location_id = locations.id ORDER BY devices.id DESC LIMIT 1")
            
        if action == "update":
            parms = yield self.dbpool.runQuery("SELECT plugins.authcode, devices.address, devices.name, locations.name FROM devices, plugins, locations WHERE devices.plugin_id = plugins.id AND devices.location_id = locations.id AND devices.id=?", [id])

        if action != "delete":
            plugin = parms[0][0]
            address = parms[0][1]
            name = parms[0][2]
            location = parms[0][3]
            
        parameters = {"plugin": plugin, 
                      "address": address,
                      "name": name,
                      "location": location}

        if self.coordinator:
            self.coordinator.send_crud_update("device", action, parameters)    

    def save_device(self, name, address, plugin_id, location_id, id=None):
        '''
        This functions saves a device in the HouseAgent database.
        @param name: the name of the device
        @param address: the address of the device
        @param plugin_id: the plugin_id of the associated plugin
        @param location_id: the location_id of the associated location
        @param id: the id of the device (in case this is an update)
        '''
        
        if not id:
            return self.dbpool.runQuery("INSERT INTO devices (name, address, plugin_id, location_id) VALUES (?, ?, ?, ?)", \
                                        (name, address, plugin_id, location_id)).addCallback(self.cb_device_crud, "create")
        else:
            return self.dbpool.runQuery("UPDATE devices SET name=?, address=?, plugin_id=?, location_id=? WHERE id=?", \
                                        (name, address, plugin_id, location_id, id)).addCallback(self.cb_device_crud, "update", id)

    def del_device(self, id):
        
        def delete(result, id):
            self.dbpool.runQuery("DELETE FROM devices WHERE id=?", [id]).addCallback(self.cb_device_crud, "delete", id, result[0][0], result[0][1], result[0][2], result[0][3])
        
        return self.dbpool.runQuery("SELECT plugins.authcode, devices.address, devices.name, locations.name FROM plugins, devices, locations " +
                                    "WHERE devices.plugin_id = plugins.id AND devices.location_id = locations.id AND devices.id=?", [id]).addCallback(delete, id)

    def del_location(self, id):
        return self.dbpool.runQuery("DELETE FROM locations WHERE id=?", [id])

    @inlineCallbacks
    def del_event(self, id):
        # Delete all parameters for this event id
        yield self.dbpool.runQuery("DELETE FROM trigger_parameters where triggers_id=" +
                                   " (select id from triggers where events_id=?)", [id])
        
        yield self.dbpool.runQuery("DELETE FROM condition_parameters where conditions_id=" +
                                   " (select id from conditions where events_id=?)" , [id])
    
        yield self.dbpool.runQuery("DELETE FROM action_parameters where actions_id=" +
                                   " (select id from actions where events_id=?)", [id])
        
        yield self.dbpool.runQuery("DELETE FROM triggers where events_id=?", [id])
        yield self.dbpool.runQuery("DELETE FROM actions where events_id=?", [id])
        yield self.dbpool.runQuery("DELETE FROM conditions where events_id=?", [id])
        
        yield self.dbpool.runQuery("DELETE FROM events where id=?", [id])

    def del_plugin(self, id):
        return self.dbpool.runQuery("DELETE FROM plugins WHERE id=?", [id])

    def query_locations(self):
        return self.dbpool.runQuery("select locations.id, locations.name, l2.name from locations " +  
                                    "left join locations as l2 on locations.parent=l2.id")

    def query_values(self):
        return self.dbpool.runQuery("SELECT current_values.name, current_values.value, devices.name, " + 
                               "current_values.lastupdate, plugins.name, devices.address, locations.name, current_values.id" + 
                               ", control_types.name, control_types.id, history FROM current_values INNER " +
                               "JOIN devices ON (current_values.device_id = devices.id) INNER JOIN plugins ON (devices.plugin_id = plugins.id) " + 
                               "LEFT OUTER JOIN locations ON (devices.location_id = locations.id) " + 
                               "LEFT OUTER JOIN control_types ON (current_values.control_type_id = control_types.id)")

    def query_devices(self):      
        return self.dbpool.runQuery("SELECT devices.id, devices.name, devices.address, plugins.name, locations.name from devices " +
                                    "INNER JOIN plugins ON (devices.plugin_id = plugins.id) " +
                                    "LEFT OUTER JOIN locations ON (devices.location_id = locations.id)")

    def query_location(self, id):
        return self.dbpool.runQuery("SELECT id, name, parent FROM locations WHERE id=?", [id])
    
    def query_plugin(self, id):
        return self.dbpool.runQuery("SELECT id, name, location_id FROM plugins WHERE id=?", [id])
    
    def query_device(self, id):
        return self.dbpool.runQuery("SELECT id, name, address, plugin_id, location_id FROM devices WHERE id=?", [id])

    def query_triggertypes(self):
        return self.dbpool.runQuery("SELECT id, name from trigger_types")

    def query_actiontypes(self):
        return self.dbpool.runQuery("SELECT id, name from action_types")
    
    def query_conditiontypes(self):
        return self.dbpool.runQuery("SELECT id, name from condition_types")
    
    def query_controltypes(self):
        return self.dbpool.runQuery("SELECT id, name from control_types")
    
    def query_controltypename(self, current_value_id):
        return self.dbpool.runQuery("select control_types.name from current_values " +
                                    "INNER JOIN controL_types ON (control_types.id = current_values.control_type_id) " +
                                    "where current_values.id=?", [current_value_id])
    
    def query_devices_simple(self):
        return self.dbpool.runQuery("SELECT id, name from devices")
    
    def query_plugintypes(self):
        return self.dbpool.runQuery("SELECT id, name from plugin_types")

    def query_historic_values(self):
        return self.dbpool.runQuery("select current_values.id, current_values.name, devices.name, current_values.history from current_values, devices where current_values.device_id = devices.id and history = 1;")

    def query_controllable_devices(self):
        return self.dbpool.runQuery("SELECT devices.name, devices.address, plugins.name, plugins.authcode, current_values.value, devices.id, control_types.name FROM current_values " +
                                    "INNER JOIN devices ON (current_values.device_id = devices.id) " +
                                    "INNER JOIN plugins ON (devices.plugin_id = plugins.id) " +
                                    "INNER JOIN control_types ON (current_values.control_type_id = control_types.id) " +
                                    "WHERE current_values.control_type_id != ''")
    
    def query_action_types_by_device_id(self, device_id):
        return self.dbpool.runQuery("SELECT current_values.id, current_values.name, control_types.name FROM current_values " +
                                    "INNER JOIN control_types ON (current_values.control_type_id = control_types.id) " +
                                    "WHERE current_values.device_id = ?", [device_id])

    def query_action_type_by_value_id(self, value_id):
        return self.dbpool.runQuery("SELECT control_types.name FROM current_values " +
                                    "INNER JOIN control_types ON (current_values.control_type_id = control_types.id) " +
                                    "WHERE current_values.id = ? LIMIT 1", [value_id])
        
    def query_values_by_device_id(self, device_id):
        return self.dbpool.runQuery("SELECT id, name from current_values WHERE device_id = '%s'" % device_id)

    def query_device_type_by_device_id(self, device_id):
        return self.dbpool.runQuery("SELECT device_types.name FROM devices " +  
                                    "INNER JOIN device_types ON (device_types.id = devices.device_type_id) " + 
                                    "WHERE devices.id = ? LIMIT 1", [device_id])

    def query_value_by_valueid(self, value_id):
        return self.dbpool.runQuery("SELECT value,name from current_values WHERE id = ? LIMIT 1", [value_id])
    
    def query_extra_valueinfo(self, value_id):
        return self.dbpool.runQuery("select devices.name, current_values.name from current_values " +
                                    "inner join devices on (current_values.device_id = devices.id) " + 
                                    "where current_values.id = ?", [value_id])

    def set_history(self, id, history):
        return self.dbpool.runQuery("UPDATE current_values SET history=? WHERE id=?", [history, id])
    
    def set_controltype(self, id, control_type):
        return self.dbpool.runQuery("UPDATE current_values SET control_type_id=? WHERE id=?", [control_type, id])

    def update_location(self, id, name, parent):
        return self.dbpool.runQuery("UPDATE locations SET name=?, parent=? WHERE id=?", [name, parent, id])
    
    def update_plugin(self, id, name, location):
        return self.dbpool.runQuery("UPDATE plugins SET name=?, location_id=? WHERE id=?", [name, location, id])
    
    def query_events(self):
        return self.dbpool.runQuery("SELECT id, name, enabled from events")

class DataHistory():
    """
    This class provides historic data logging capabilities for HouseAgent.
    """
    def __init__(self, value_name=None, value_id=None, value_value=None, type=None, heartbeat=None, time=None):
        
        self.value_name     = value_name
        self.value_id       = value_id
        self.type           = type
        self.value_value    = value_value
        self.heartbeat      = heartbeat
        self.time           = time
 
        if not os.path.exists(os.path.join("history/", "%s.rrd" % self.value_id)):
            print "RRD does not exist, create"
            self.create()
        else:
            print "RRD exists, insert"
            self.insert()
        
    def insert(self):
        """ 
        Inserts new data in the RRD database 
        """
        rrd = RRD(os.path.join("history/", "%s.rrd" % self.value_id))
        rrd.bufferValue(self.time, self.value_value)
        rrd.update()
        print self.time, self.value_value
        
    def fetch(self, start=None, end=None, resolution=None):
        """
        Fetch data from the RRD database.
        """
        rrd = RRD("history/108732.rrd")
        print rrd.fetch(resolution=300, start='-1h', end=self.epoch_now())         
    
    def create(self):
        """ 
        Creates a new RRD database 
        """
        ds1 = DS(dsName=self.value_name, dsType=self.type, heartbeat=self.heartbeat)
        dss = [ds1]
              
        rras = []
        # 1 days-worth of n heartbeat samples --> 60/1 * 24
        rra1 = RRA(cf='AVERAGE', xff=0.5, steps=1, rows=int(self.heartbeat/1.0 * 24)) 
        # 7 days-worth of n heartbeat samples --> 60/5 * 24 * 7
        rra2 = RRA(cf='AVERAGE', xff=0.5, steps=5, rows=int(self.heartbeat/5.0 * 24 * 7))
        # 30 days-worth of n heartbeat samples --> 60/60 * 24 * 30
        rra3 = RRA(cf='AVERAGE', xff=0.5, steps=60, rows=int(self.heartbeat/60.0 * 24 * 30))
        # 365 days worth of n heartbeat samples --> 60/120 * 24 * 365
        rra4 = RRA(cf='AVERAGE', xff=0.5, steps=120, rows=int(self.heartbeat/120.0 * 24 * 365))
        # 10 years worth of n heartbeat samples --> 60/180 * 24 * 365 * 10
        rra5 = RRA(cf='AVERAGE', xff=0.5, steps=180, rows=int(self.heartbeat/180.0 * 24 * 365 * 10))
        
        rras.extend([rra1, rra2, rra3, rra4, rra5])

        rrd = RRD(os.path.join("history/", "%s.rrd" % self.value_id), step=self.heartbeat, 
                    ds=dss, rra=rras, start=self.time)
        rrd.create(debug=False)

    def epoch_now(self):
        """ 
        This is a little helper method which get's the current time in epoch seconds.
        The datetime module really needs one... 
        """
        t = datetime.datetime.now()
        return int(time.mktime(t.timetuple()))
    
# Testing
#history = DataHistory('Temperature', '20202', 'GAUGE', 60)
#history.create()

# Test fetch
#history = DataHistory(value_id=108732)       
#history.fetch()
