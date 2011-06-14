import database
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.scheduling.cron import CronSchedule
from twisted.scheduling.task import ScheduledCall

db = database.Database()

class EventHandler(object):
    
    def __init__(self, coordinator):
        
        self._absolute_time_schedule_calls = []
        self._triggers = []
        self._actions = []
        self._conditions = []
        
        # Start the eventhandler
        self._load_actions()
        self._load_conditions()
        self._load_triggers()
        
        # let the coordinator know we are here
        coordinator.register_eventengine(self)
        self._coordinator = coordinator
    
    @inlineCallbacks
    def _load_triggers(self):
        ''' 
        This function loads all the triggers from the database.
        '''
        
        # Stop any outstanding absolute time triggers in case of a reload.
        for schedule in self._absolute_time_schedule_calls:
            schedule.stop()
            
        self._absolute_time_schedule_calls = []
        
        triggers = yield db.query_triggers()
        
        for trigger in triggers:   
            t = Trigger(trigger[1], trigger[2], trigger[3])
            
            # get trigger parameters
            trigger_parameters = yield db.query_trigger_parameters(trigger[0])
            
            for param in trigger_parameters:
                if param[0] == "cron":
                    t.cron = param[1]
                elif param[0] == "current_value_id":
                    t.current_value_id = param[1]
                elif param[0] == "condition":
                    t.condition = param[1]
                elif param[0] == "condition_value":
                    t.condition_value = param[1]
            
            # Handle absolute time directly, and schedule. No need to keep track of this.
            if trigger[1] == "Absolute time":         

                c = CronSchedule(t.cron)
                print c.getNextEntry()
                s = ScheduledCall(f=self._absolute_time_triggered, eventid=trigger[2], conditions=trigger[3])
                s.start(c)
                
                self._absolute_time_schedule_calls.append(s)
                continue
            
            self._triggers.append(t)
    
    @inlineCallbacks
    def _load_actions(self):
        ''' 
        This function loads all the actions from the database.
        '''              
        actions = yield db.query_actions()

        for action in actions:
            a = Action(action[1], action[2])
            
            action_parameters = yield db.query_action_parameters(action[0])
            for param in action_parameters:
                if param[0] == "device":
                    a.device = param[1]
                elif param[0] == "control_value":
                    a.control_value = param[1]
                elif param[0] == "command":
                    a.command = param[1]
                
            if action[1] == "Device action":
                # fetch extra device properties
                device_properties = yield db.query_device_routing_by_id(a.device)
                a.address = device_properties[0][0]
                a.plugin_id = device_properties[0][1]
                
                # fetch control_type
                control_type = yield db.query_controltypename(a.control_value)
                a.control_type = control_type[0][0]
            
            self._actions.append(a)
        
    @inlineCallbacks
    def _load_conditions(self):
        ''' 
        This function loads conditions from the database.
        '''
        conditions = yield db.query_conditions()
        
        for condition in conditions:
            c = Condition(condition[1], condition[2])
            
            condition_parameters = yield db.query_condition_parameters(condition[0])
            
            for param in condition_parameters:
                if param[0] == "condition":
                    c.condition = param[1]
                elif param[0] == "condition_value":
                    c.condition_value = param[1]
                elif param[0] == "current_values_id":
                    c.current_values_id = param[1]

            self._conditions.append(c)

    def reload(self):
        '''
        This allows an external caller to reload the event engine.
        All triggers, conditions and actions will be reloaded.
        '''
        self._triggers = []
        self._actions = []
        self.__conditions = []
        
        self._load_conditions()
        self._load_triggers()
        self._load_actions()
        
    @inlineCallbacks
    def device_value_changed(self, value_id, value):
        '''
        Callback from the coordinator when a device value has been changed.
        '''
        for t in self._triggers:

            if t.type == "Device value change" and int(t.current_value_id) == int(value_id):
                
                matching = True
                
                if t.condition == "eq":
                    if value != t.condition_value:
                        matching = False
                elif t.condition == "ne":
                    if value == t.condition_value:
                        matching = False
                elif t.condition == "gt":
                    if float(value) < float(t.condition_value):
                        matching = False
                elif t.condition == "lt":
                    if float(value) > float(t.condition_value):
                        matching = False       
                        
                if matching:
                    # check conditions
                    if t.conditions:           
                        condition_check = yield self._check_conditions(t.event_id)
                        
                        if condition_check:
                            self._run_actions(t.event_id)
                    else:
                        # no conditions, just run the actions
                        self._run_actions(t.event_id)                     

    @inlineCallbacks
    def _absolute_time_triggered(self, eventid, conditions):
        '''
        This function is triggered when a absolute time value has been reached. 
        E.g. this function can be triggered on 10:00 every day. 
        It then checks for any conditions on the trigger and then executes actions
        associated with the event.
        '''

        # check conditions
        if conditions:           
            condition_check = yield self._check_conditions(eventid)
            
            if condition_check:
                self._run_actions(eventid)
        else:
            # no conditions, just run the actions
            self._run_actions(eventid)
            
    def _run_actions(self, eventid):
        '''
        This runs all the actions associated with a certain eventid.
        '''
        print "should run action"
        for a in self._actions:
            if a.event_id == eventid:   
                if a.type == "Device action" and a.control_type == "CONTROL_TYPE_ON_OFF" and int(a.command) == 1:
                    self._coordinator.send_poweron(a.plugin_id, a.address)
                elif a.type == "Device action" and a.control_type == "CONTROL_TYPE_THERMOSTAT":
                    self._coordinator.send_thermostat_setpoint(a.plugin_id, a.address, a.command)

    @inlineCallbacks            
    def _check_conditions(self, eventid):
        '''
        This function checks conditions for a certain eventid.
        By default conditions are AND'ed together, which means that all 
        conditions must return true in order for this function to return true.
        '''   
        matching = True
        
        for c in self._conditions:            
            if c.event_id == eventid:
                
                if c.type == "Device value":
                    
                    # query current value
                    actual_value = yield db.query_value_by_valueid(c.current_values_id)
                    
                    # check conditions, note that these are actually checked reversed...
                    if c.condition == "eq":
                        if actual_value[0][0] != c.condition_value:
                            matching = False
                    elif c.condition == "ne":
                        if actual_value[0][0] == c.condition_value:
                            matching = False
                    elif c.condition == "gt":
                        if float(actual_value[0][0]) < float(c.condition_value):
                            matching = False
                    elif c.condition == "lt":
                        if float(actual_value[0][0]) > float(c.condition_value):
                            matching = False              
                            
            if matching == False:
                break
        
        returnValue(matching)

class Condition(object):
    '''
    This class is a skeleton class for a condition.
    '''  
    def __init__(self, type=None, event_id=None):
        self.type = type
        self.event_id = event_id
        self.condition = None
        self.condition_value = None
        self.current_values_id = None
        
        # Only used for web page output
        self.device = None
        self.value_name = None
        
class Trigger(object):
    '''
    This class ia a skeleton class for a trigger.
    '''  
    def __init__(self, type=None, event_id=None, conditions=False):
        self.type = type
        self.event_id = event_id
        self.conditions = conditions
        self.cron = None
        self.current_value_id = None
        self.condition = None
        self.condition_value = None
        
        # Only used for web page output
        self.device = None
        self.value_name = None
        
    def __str__(self):
        return "type: [{0}] event_id: [{1}] conditions: {2} cron: {3} current_value_id: {4} condition: {5} condition_value: {6}".format(self.type, self.event_id, self.conditions, self.cron, 
                                              self.current_value_id, self.condition, self.condition_value)
        
class Action(object):
    '''
    This class is a skeleton class for an action.
    '''
    def __init__(self, type=None, event_id=None):
        self.type = type
        self.event_id = event_id
        self.plugin_id = None
        self.address = None
        self.control_type = None
        self.device = None
        self.control_value = None
        self.command = None
        self.control_value_name = None