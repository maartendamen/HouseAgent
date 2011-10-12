'''
Database subclass for HouseAgent running on FLASH drives

Created on Oct 5, 2011
@author: Daniel Berenguer
'''

from database import Database, DataHistory
from twisted.internet import reactor, defer
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall

import datetime


class DatabaseFlash(Database):
    '''
    HouseAgent database optimized for flash drives.
    This database subclass caches the value updates in a list by means of a CurrentValue object.
    Then, "in-memory" values are saved back to the current_values table whenever a query is
    launched from the web or periodically 
    '''              
    def __init__(self, log, interval):
        '''
        Class constructor
        
        @param log: logging object
        @param interval: elapsed seconds between periodic data saves (cache to database)
        '''
        Database.__init__(self, log)

        # Create list of current values
        self.currValues = CurrentValues(self.dbpool)

        # Periodic write of current values in database
        if interval > 0:
            lp = LoopingCall(self.currValues.saveValuesInDB)
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
        
        current_value = yield self.currValues.queryStaticData(name=name, device_id=device_id)
    
        try:
            value_id = current_value[0][0]
        except:
            value_id = None
    
        # If current value found in database
        if value_id:
            # Get current value from list
            currVal = self.currValues.getCurrentValue(value_id)
            if currVal is not None:
                # Update value
                currVal.value = value
                currVal.lastUpdate = updatetime
                
            # Log value?
            if current_value[0][2] not in (0, None):
                DataHistory("data", value_id, value, "GAUGE", 60, int(time))                
        else:
            # Insert new row in current_values
            yield self.currValues.insertValueinDB(name, value, address, device_id, pluginid, updatetime)
            # Query last inserted row
            current_value = yield self.currValues.queryStaticData(name=name, device_id=device_id)
            value_id = current_value[0][0]
            # Add new value to the list
            currVal = CurrentValue(value_id, value, updatetime)
            self.currValues.addValue(currVal)
                        
        returnValue(value_id)
               

    def query_values(self):
        """
        Query current values
        
        @return List of values
        """
        # Update database from current values in memory
        self.currValues.saveValuesInDB()
        # Query database
        return Database.query_values(self)


    def query_controllable_devices(self):
        """
        Query controllable values
        
        @return list of values
        """
        # Update database from current values in memory
        self.currValues.saveValuesInDB()
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
        def getResult():
            # Query static data (format of the output: [id, name, history])
            value = yield self.currValues.queryStaticData(id=value_id)
            # Get actual current value
            currVal = self.currValues.getCurrentValue(value_id)
            if currVal is not None:
                result = [(currVal.value, value[0][0])]
                d.callback(result)
       
        reactor.callLater(0, getResult)               
        return d
   
        
class CurrentValue:
    """
    Class representation of current value
    """
    def __init__(self, valId, value, lastUpdate):
        """
        Class constructor
        
        @param valId: id of the table row (current_value) within SQLite
        @param value: current value in string format
        @param lastUpdate: last update time
        """
        ## id of the table row within SQLite
        self.id = valId
        ## Current value in string format
        self.value = value
        ## Last update time
        self.lastUpdate = lastUpdate
        
        
class CurrentValues:
    """
    HouseAgent current values stored in list
    """
    def _queryCurrentValuesTable(self):
        """
        Query existing current_values table
        """
        queryStr = "SELECT id, value, lastupdate from current_values"
                    
        self.connPool.runQuery(queryStr).addCallback(self._cb_QueryResult, "GETDBDATA")

    
    def _cb_QueryResult(self, result, action):
        """
        Result of the last query SQLite query received
        
        @param result: Result of the last query
        @param action: Action to be deployed
        """
        if action == "GETDBDATA":
            self.lstCurrValues = []
            for row in result:
                currValue = CurrentValue(row[0], row[1], row[2])
                self.lstCurrValues.append(currValue)


    def addValue(self, currValue):
        """
        Add new value to the list
        
        @param currValue: Current value to be added
        """
        self.lstCurrValues.append(currValue)
        

    def getCurrentValue(self, id):
        """
        Get current value from list
        
        @param id: Value ID
        
        @return Current value entry or None if no value is found
        """
        for currVal in self.lstCurrValues:
            if currVal.id == id:
                return currVal                
        return None
    
    
    def queryStaticData(self, value_id=None, name=None, device_id=None):
        """
        Query static data about a given value in current_values
        
        @param value_id: Value ID
        @param name: NAme fo the value
        @param device_id: Device ID
        
        @return Deferred object to the result of this query. Format of the result:
        [id, name, history]
        """
        if value_id is not None:
            return self.connPool.runQuery("SELECT id, name, history from current_values WHERE id = ? LIMIT 1", [value_id])
        else:
            return self.connPool.runQuery("select id, name, history from current_values where name=? AND device_id=? LIMIT 1", (name, device_id))

    
    @inlineCallbacks
    def insertValueinDB(self, name, value, address, plugin_id, updatetime):
        """
        Insert new value row in the table. Get the id of the new inserted row
        
        @param name: Name of the value
        @param value: Current value
        @param address: Address of the device
        @param plugin_id: ID of the plugin
        @param updatetime: Last update time for the current value
        
        @return deferred object to the result of the query
        """
        # Insert new value into current_values
        return self.connPool.runQuery("INSERT INTO current_values (name, value, device_id, lastupdate) VALUES (?, ?, (select id from devices where address=? AND plugin_id=?),  ?)", (name, value, address, plugin_id, updatetime))

    
    @inlineCallbacks
    def saveValuesInDB(self):
        """
        Save values in database. Only modified values are been written
        """
        # Query database first
        queryStr = "SELECT id, value, lastupdate from current_values"                    
        values = yield self.connPool.runQuery(queryStr)
        start = True
        update = False
        valStr = ""
        timeStr = ""
        idStr = "("
        
        for i, currVal in enumerate(self.lstCurrValues):
            # Value changed?
            id = values[i][0]
            oldVal = values[i][1]
            
            if (currVal.id == id) and (currVal.value != oldVal):
                if not update:
                    update = True               
                if start:
                    start = False
                else:
                    idStr += ","
                idStr += str(currVal.id)
                valStr += "WHEN " + str(currVal.id) + " THEN \"" + str(currVal.value) + "\"\n"
                timeStr += "WHEN " + str(currVal.id) + " THEN \"" + str(currVal.lastUpdate) + "\"\n"

        
        if not update:
            return
        
        idStr += ")"
        queryStr = "UPDATE current_values SET value = CASE id\n"
        queryStr += valStr
        queryStr += "END,\n"
        queryStr += "lastupdate = CASE id\n"
        queryStr += timeStr
        queryStr += "END\n"        
        queryStr += "WHERE id IN " + idStr
        
        # Run query
        yield self.connPool.runQuery(queryStr)
              

    def __init__(self, connPool):
        """
        Class constructor
        
        @param connPool: Database connection pool
        """
        ## Connection pool to data base
        self.connPool = connPool
        ## List of current values
        self.lstCurrValues = None
        # Query current_values table
        self._queryCurrentValuesTable()
