'''
Database subclass for HouseAgent running on FLASH drives

Created on Oct 5, 2011
@author: Daniel Berenguer
'''

from database import Database
#from database import Database, DataHistory
from twisted.internet import reactor, defer
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall

import datetime
import sys


class DatabaseFlash(Database):
    '''
    HouseAgent database optimized for flash drives.
    This database subclass caches the value updates in a list by means of a CurrentValueTable
    object. Then, "in-memory" values are saved back to the current_values table whenever a
    query is launched from the web or periodically 
    '''              
    def __init__(self, log, db_location, interval):
        '''
        Class constructor
        
        @param log: logging object
        @param interval: elapsed seconds between periodic data saves (cache to database)
        '''
        Database.__init__(self, log, db_location)
        # Create list of current values
        self.curr_values = CurrentValueTable(self.dbpool)

        # Periodic write of current values in database
        if interval > 0:
            lp = LoopingCall(self.curr_values.save_values_in_db)
            lp.start(interval, False)


    @inlineCallbacks
    def update_or_add_value(self, name, value, pluginid, address, time=None):
        '''
        Overriden method
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
        device = yield self.dbpool.runQuery('select id from devices WHERE plugin_id = ? and address = ? LIMIT 1', (pluginid, address) )

        try:
            device_id = device[0][0]
        except:
            returnValue('') # device does not exist
        
        current_value = yield self.curr_values.query_static_data(name=name, device_id=device_id)
    
        try:
            value_id = current_value[0][0]
        except:
            value_id = None
    
        # If current value found in database
        if value_id:
            # Get current value from list
            curr_val = self.curr_values.get_current_value(value_id)
            if curr_val is not None:
                # Update value
                curr_val.value = value
                curr_val.last_update = updatetime

            # XXX: need to be rewriten
            # Log value?
            if current_value[0][2] not in (0, None):
                DataHistory("data", value_id, value, "GAUGE", 60, int(time))                
        else:
            # Insert new row in current_values
            yield self.curr_values.insert_value_in_db(name, value, address, pluginid, updatetime)
            # Query last inserted row
            current_value = yield self.curr_values.query_static_data(name=name, device_id=device_id)
            value_id = current_value[0][0]
            # Add new value to the list
            curr_val = CurrentValue(value_id, value, updatetime)
            self.curr_values.add_value(curr_val)
                        
        returnValue(value_id)
               

    def query_values(self):
        """
        Query current values
        Cached values are saved into database each time this method is called
        
        @return List of values
        """
        # Update database from current values in memory
        self.curr_values.save_values_in_db()
        # Query database
        return Database.query_values(self)


    def query_controllable_devices(self):
        """
        Query controllable values
        Cached values are saved into database each time this method is called
        
        @return list of values
        """
        # Update database from current values in memory
        self.curr_values.save_values_in_db()
        # Query database
        return Database.query_controllable_devices(self)

        
    def query_value_by_valueid(self, value_id):
        """
        Query a given value
        
        @param value_id: Value ID
        
        @return Deferred object
        """
        d = defer.Deferred()
    
        @inlineCallbacks
        def get_result():
            # Query static data (format of the output: [id, name, history])
            value = yield self.curr_values.query_static_data(id=value_id)
            # Get actual current value
            curr_val = self.curr_values.get_current_value(value_id)
            if curr_val is not None:
                result = [(curr_val.value, value[0][0])]
                d.callback(result)
       
        reactor.callLater(0, get_result)               
        return d
   
        
class CurrentValue:
    """
    Class representation of current value
    """
    def __init__(self, val_id, value, last_update):
        """
        Class constructor
        
        @param val_id: id of the table row (current_value) within SQLite
        @param value: current value in string format
        @param last_update: last update time
        """
        ## id of the table row within SQLite
        self.id = val_id
        ## Current value in string format
        self.value = value
        ## Last update time
        self.last_update = last_update
        
        
class CurrentValueTable:
    """
    Class representing HouseAgent's current_value table with all the live data (value and time)
    being stored in an in-memory list
    """
    def __init__(self, conn_pool):
        """
        Class constructor
        
        @param conn_pool: Database connection pool
        """
        ## Connection pool to data base
        self.conn_pool = conn_pool
        ## List of current values
        self.lst_curr_values = None
        # Query current_values table
        self._query_current_values_table()
    
    def _query_current_values_table(self):
        """
        Query existing current_values table
        """
        query_str = "SELECT id, value, lastupdate from current_values"
                    
        self.conn_pool.runQuery(query_str).addCallback(self._cb_query_result, "GETDBDATA")

    
    def _cb_query_result(self, result, action):
        """
        Result of the last query SQLite query received
        
        @param result: Result of the last query
        @param action: Action to be deployed
        """
        if action == "GETDBDATA":
            # Fill the "in_memory" list of "live" data
            self.lst_curr_values = []
            for row in result:
                curr_value = CurrentValue(row[0], row[1], row[2])
                self.add_value(curr_value)


    def add_value(self, curr_value):
        """
        Add new value to the list
        
        @param curr_value: Current value to be added
        """
        self.lst_curr_values.append(curr_value)
        

    def get_current_value(self, val_id):
        """
        Get current value from list
        
        @param id: Value ID
        
        @return Current value entry or None if no value is found
        """
        for curr_val in self.lst_curr_values:
            if curr_val.id == val_id:
                return curr_val                
        return None
    
    
    def query_static_data(self, value_id=None, name=None, device_id=None):
        """
        Query static data about a given value in current_values
        
        @param value_id: Value ID
        @param name: NAme fo the value
        @param device_id: Device ID
        
        @return Deferred object to the result of this query. Format of the result:
        [id, name, history]
        """
        if value_id is not None:
            return self.conn_pool.runQuery("SELECT id, name, history from current_values WHERE id = ? LIMIT 1", [value_id])
        else:
            return self.conn_pool.runQuery("select id, name, history from current_values where name=? AND device_id=? LIMIT 1", (name, device_id))

    
    def insert_value_in_db(self, name, value, address, plugin_id, update_time):
        """
        Insert new value row in the table. Get the id of the new inserted row
        
        @param name: Name of the value
        @param value: Current value
        @param address: Address of the device
        @param plugin_id: ID of the plugin
        @param update_time: Last update time for the current value
        
        @return deferred object to the result of the query
        """
        # Insert new value into current_values
        return self.conn_pool.runQuery("INSERT INTO current_values (name, value, device_id, lastupdate) VALUES (?, ?, (select id from devices where address=? AND plugin_id=?),  ?)", (name, value, address, plugin_id, update_time))


    def _save_table(self, txn):
        """
        Save values in current_values table. Only modified values/timestamps are been written
        This method has to be run within a runInteraction call
        """
        # Query database first
        querystr = "SELECT id, value, lastupdate from current_values"
        values = txn.execute(querystr).fetchall()
        
        # Prepare query for updating values and timestamps
        querystr = "UPDATE current_values SET value=?, lastupdate=? WHERE id=?"
        for i, curr_val in enumerate(self.lst_curr_values):
            # Value changed?
            val_id = values[i][0]
            oldval = values[i][1]
            oldtime = values[i][2]
            
            # Run update only forthose values that have been updated
            if (curr_val.id == val_id) and ((curr_val.value != oldval) or (curr_val.last_update != oldtime)):
                txn.execute(querystr, [curr_val.value, curr_val.last_update, curr_val.id])
                
            
    def save_values_in_db(self):
        """
        Save values in database
        """
        try:
            # Run database operations in a separate thread
            return self.conn_pool.runInteraction(self._save_table)
        except:
            self.log.error("Unable to write current values in database (%s)" % sys.exc_info()[1])
    
