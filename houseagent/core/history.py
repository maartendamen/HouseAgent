from twisted.internet import task
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.enterprise.adbapi import ConnectionPool
from houseagent.utils.config import Config
from houseagent.plugins import pluginapi

# Fix to support both twisted.scheduling and txscheduling (new version)
try:
    from txscheduling.cron import CronSchedule
    from txscheduling.task import ScheduledCall
except ImportError:
    from twisted.scheduling.cron import CronSchedule
    from twisted.scheduling.task import ScheduledCall

import datetime
import os
import sys
import sqlite3

# TODO:
# * better logging
# * code cleanup (remove debug 'print' statements)

class HistoryCollector():
    def __init__(self, database, histagg):
        self.db = database
        self.histagg = histagg
        database.histcollector = self

        self.log = pluginapi.Logging("Collector")

        self._periods = {}
        self._schedules = {}
        self._scheduled_tasks = {}

        # wait for data from DB
        deferredlist = []
        deferredlist.append(self._load_periods())
        deferredlist.append(self._load_schedules())

        d = defer.gatherResults(deferredlist)
        d.addCallback(self.do)

    @inlineCallbacks
    def _load_periods(self):
        periods = yield self.db.query_history_periods()

        for period in periods:
            self._periods[period[0]] = {"name": period[1], "secs": period[2],\
                                        "sysflag": period[3]}


    @inlineCallbacks
    def _load_schedules(self):
        schedules = yield self.db.query_history_schedules()

        for schedule in schedules:
            self._schedules[schedule[0]] = {"name": schedule[1],\
                                            "period_id": schedule[2],\
                                            "type_id": schedule[3]}


    def cb_register_schedule(self, id, period):
        # reload schedule when someone change the settings on web(Values)
        def _register(result, id, period):
            schedule = self._resolve_schedule(id)
            period = self._resolve_period(schedule)
            self._start_schedule(id, schedule, period)
            self.histagg._start_schedule(id, schedule, period)

        # fetch periods and current schedules, something may have changed
        deferredlist = []
        deferredlist.append(self._load_periods())
        deferredlist.append(self._load_schedules())

        d = defer.gatherResults(deferredlist)
        d.addCallback(_register, id, period)


    def cb_unregister_schedule(self, id):
        # reload schedule when someone change the settings on web(Values)
        self.log.debug("Sheduled tasks: %s" % self._scheduled_tasks)
        try:
            self._stop_schedule(id)
            self.histagg._stop_schedule(id)
        except KeyError: pass # schedule is not scheduled


    def _resolve_schedule(self, id):
        s = self._schedules[id]
        return s

    def _resolve_period(self, schedule):
        p = self._periods[schedule["period_id"]]
        return p

    def _start_schedule(self, id, schedule, period):
        if period["secs"] == 0:
            self.log.info("Collection for value: %s is disabled." % schedule["name"])
        elif period["secs"] >= 300 and period["secs"] <= 86400:
            t = task.LoopingCall(self.collect, id, schedule["name"], period["name"])
            # Start collection after next period run
            t.start(period["secs"], False)
            self._scheduled_tasks[id] = {"obj": t}
        else:
            self.log.warning("Invalid collection period (%s)" % period["secs"])


    def _stop_schedule(self, id):
        self._scheduled_tasks[id]["obj"].stop()
        del self._scheduled_tasks[id]


    def collect(self, value_id, schedule_name, period_name):
        self.log.debug("Collecting value for: %s in %s period" % (schedule_name, period_name))
        self.db.collect_history_values(value_id)


    def cleanup(self):
        self.log.debug("Cleaning 1 day old values from history_values table.")
        self.db.cleanup_history_values()


    def do(self, result):
        for val_id in self._schedules:
            schedule = self._resolve_schedule(val_id)
            period = self._resolve_period(schedule)
            self._start_schedule(val_id, schedule, period)

        # Try to cleanup history_values every 2 hours
        t = task.LoopingCall(self.cleanup)
        t.start(7200, False)

        self.log.debug("Sheduled tasks: %s" % self._scheduled_tasks)



class HistoryAggregator():

    def __init__(self, database):
        conf = Config()

        self.db = database
        self.cur_month = datetime.datetime.strftime(datetime.datetime.now(), "%m")
        self.dba = DatabaseArchive(conf.general.dbpatharchive, \
                                    conf.general.dbfile, [])
        self.log = pluginapi.Logging("Aggregator")

        self._types = {}
        self._schedules = {}
        self._periods = {}
        self._scheduled_tasks = {}
        # aggregation periods (ScheduledCalls setup)
        self._agg_periods = {"day": "1 * * * *",        # every hour
                             "month": "5 */6 * * *",    # every six hours
                             "year": "10 0 * * *"}      # every night


        # wait for data from DB
        deferredlist = []
        deferredlist.append(self._load_history_types())
        deferredlist.append(self._load_schedules())
        deferredlist.append(self._load_periods())

        d = defer.gatherResults(deferredlist)
        d.addCallback(self.do)



    @inlineCallbacks
    def _load_history_types(self):
        types = yield self.db.query_history_types()

        for type in types:
            self._types[type[0]] = {"type": type[1]}


    @inlineCallbacks
    def _load_schedules(self):
        schedules = yield self.db.query_history_schedules()

        for schedule in schedules:
            self._schedules[schedule[0]] = {"name": schedule[1],\
                                            "period_id": schedule[2],\
                                            "type_id": schedule[3]}


    @inlineCallbacks
    def _load_periods(self):
        periods = yield self.db.query_history_periods()

        for period in periods:
            self._periods[period[0]] = {"name": period[1],\
                                        "secs": period[2],\
                                        "sysflag": period[3]}


    def _resolve_schedule(self, id):
        s = self._schedules[id]
        return s

    def _resolve_period(self, schedule):
        p = self._periods[schedule["period_id"]]
        return p

    def _resolve_type(self, schedule):
        t = self._types[schedule["type_id"]]["type"]
        return t


    def _start_schedule(self, id, schedule, period):
            # check if the schedule is disabled or not
            if period["secs"] != 0:
                if not self._scheduled_tasks.has_key(id):
                    self._scheduled_tasks[id] = []
                val_type = self._resolve_type(schedule)

                for p in self._agg_periods:
                    cron = CronSchedule(self._agg_periods[p])
                    if p == "day":
                        t = ScheduledCall(self._aggregate_day, id, val_type)
                        t.start(cron)
                        self._scheduled_tasks[id].append(t)
                    elif p == "month":
                        t = ScheduledCall(self._aggregate_month, id)
                        t.start(cron)
                        self._scheduled_tasks[id].append(t)
                    elif p == "year":
                        t = ScheduledCall(self._aggregate_year, id)
                        t.start(cron)
                        self._scheduled_tasks[id].append(t)
                    else:
                        self.log.warning("Unsupported period (%s)" % p)

            self.log.debug("Scheduled tasks: %s" % self._scheduled_tasks)


    def _stop_schedule(self, id):
        for t in self._scheduled_tasks[id]:
            t.stop()

        del self._scheduled_tasks[id]


    def _aggregate_day(self, val_id, val_type):
        self.dba.aggregate_day(val_id, val_type)

    def _aggregate_month(self, val_id):
        self.dba.aggregate_month(val_id)

    def _aggregate_year(self, val_id):
        self.dba.aggregate_year(val_id)

        # check if the new month come
        next_month = datetime.datetime.strftime(datetime.datetime.now(), "%m")
        if next_month > self.cur_month:
            self.dba.close() # close old DB
            self.dba = DatabaseArchive(conf.general.dbpatharchive, \
                                       conf.general.dbfile, [])


    def do(self, result):
        for val_id in self._schedules:
            schedule = self._resolve_schedule(val_id)
            period = self._resolve_period(schedule)

            # start enabled shedules
            self._start_schedule(val_id, schedule, period)


            

class DatabaseArchive():
    """
    Class for manipulating with archive databases, eg. creating, reading..
    """

    def __init__(self, archive_db_location, main_db, db_array=[]):
        """
        @param db_location: directory which contains archive db files
        @param db_array: array with YYYY_MM values used to create a pointers to the databases
        """
        self.log = pluginapi.Logging("Test")

        self.type = "sqlite3"

        self.attached_dbs = 0
        self.max_attached_dbs = 7

        self.main_db = main_db
        self.archive_db_location = archive_db_location
        self.curr_date = datetime.datetime.strftime(datetime.datetime.now(), "%Y_%m")

        if len(db_array) == 0:
            # not a specific archive(s) lookup, use the db for current month
            self.db_name = "archive_%s.db" % self.curr_date
            self.db_path = os.path.join(self.archive_db_location, self.db_name)
        else:
            # XXX: need to rewrite this part
            # code for opening more than one archive db file
            # attach_archive_db(YYYY_MM)
            # attach_archive_db(YYYY_MM)
            pass

        self.check_archive_db()
        self.attach_main_db(self.main_db)


    def check_archive_db(self):
        """
        create non-existent archive_YYYY_MM db file
        """
        if os.path.exists(self.db_path):
            self.dbpool = ConnectionPool(self.type, self.db_path, check_same_thread=False, cp_max=1)
        else:
            self.create_archive_db()
            try:
                self.dbpool = ConnectionPool(self.type, self.db_path, check_same_thread=False, cp_max=1)
            except Exception, err:
                self.log.debug("dbpool exc: %s" % err)
                os._exit(1)
            self.prepare_archive_db()


    def create_archive_db(self):
        _db_name = "archive_%s.db" % self.curr_date
        _db_path = os.path.join(self.archive_db_location, _db_name)
        try:
            self.log.debug("create_archive_db: %s" % _db_name) 
            fd = os.open(_db_path, os.O_CREAT, 0644)
        except Exception, err:
            self.log.critical("Cannot create archive db '%s': %s" % (_db_name, err))
            sys.exit(1) # exit HouseAgent

        os.fsync(fd) # don't trust to the automatic fs sync mechanism
        os.close(fd)


    def prepare_archive_db(self):
        return self.dbpool.runInteraction(self._prepare_archive_db)

    def _prepare_archive_db(self, txn):
        self.log.debug("Creating new archive db.")
        try:
            txn.execute("CREATE TABLE day (id INTEGER, value REAL DEFAULT 0.00, min REAL DEFAULT 0.00, avg REAL DEFAULT 0.00, max REAL DEFAULT 0.00, type VARCHAR(50), date_from DATETIME, date_to DATETIME);")
            txn.execute("CREATE TABLE month (id INTEGER, value REAL DEFAULT 0.00, min REAL DEFAULT 0.00, avg REAL DEFAULT 0.00, max REAL DEFAULT 0.00, type VARCHAR(50), date_from DATETIME, date_to DATETIME);")
            txn.execute("CREATE TABLE year (id INTEGER, value REAL DEFAULT 0.00, min REAL DEFAULT 0.00, avg REAL DEFAULT 0.00, max REAL DEFAULT 0.00, type VARCHAR(50), date_from DATETIME, date_to DATETIME);")
        except:
            self.log.error("Database schema upgrade failed (%s)" % sys.exc_info()[1])


    def attach_main_db(self, main_db):
        """
        Attach main houseagent database for queries on history_values table (day aggregations)
        """
        self.attached_dbs = 1
        return self.dbpool.runQuery("ATTACH DATABASE '%s' AS houseagent;" % main_db)


    def attach_archive_db(self, db_path):
        # CAUTION: SQLITE_LIMIT_ATTACHED is set to max 7 DB!!
        # take care of this
        pass 

    def close(self):
        self.dbpool.close()

    def aggregate_day(self, val_id, val_type):
        date_to = datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d %H:00:00")
        date_from = datetime.datetime.strftime(datetime.datetime.now() - datetime.timedelta(hours=1), "%Y-%m-%d %H:00:00")
        return self.dbpool.runQuery("INSERT INTO \
                        day(id, value, min, avg, \
                           max, type, date_from, date_to) \
                        SELECT value_id AS id, ROUND(value,2) AS value, \
                               ROUND(MIN(value),2) AS min, \
                               ROUND(AVG(value), 2) AS avg, \
                               ROUND(MAX(value),2) AS max, \
                               '%s', '%s', '%s'\
                        FROM houseagent.history_values \
                        WHERE value_id='%s' AND created_at >= '%s' AND created_at < '%s';" \
                        % (val_type, date_from, date_to, val_id, date_from, date_to))


    def aggregate_month(self, val_id):
        date_to = datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d %H:00:00")
        date_from = datetime.datetime.strftime(datetime.datetime.now() - datetime.timedelta(hours=6), "%Y-%m-%d %H:00:00")
        return self.dbpool.runQuery("INSERT INTO \
                        month(id, value, min, avg, \
                           max, type, date_from, date_to) \
                        SELECT id, ROUND(value,2) AS value, \
                               ROUND(MIN(value),2) AS min, \
                               ROUND(AVG(value), 2) AS avg, \
                               ROUND(MAX(value),2) AS max, \
                               type, '%s', '%s'\
                        FROM day \
                        WHERE id='%s' AND date_from >= '%s' AND date_to < '%s';" \
                        % (date_from, date_to, val_id, date_from, date_to))


    def aggregate_year(self, val_id):
        date_to = datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d %H:00:00")
        date_from = datetime.datetime.strftime(datetime.datetime.now() - datetime.timedelta(hours=24), "%Y-%m-%d %H:00:00")
        return self.dbpool.runQuery("INSERT INTO \
                        year(id, value, min, avg, \
                           max, type, date_from, date_to) \
                        SELECT id, ROUND(value,2) AS value, \
                               ROUND(MIN(value),2) AS min, \
                               ROUND(AVG(value), 2) AS avg, \
                               ROUND(MAX(value),2) AS max, \
                               type, '%s', '%s'\
                        FROM month \
                        WHERE id='%s' AND date_from >= '%s' AND date_to < '%s';" \
                        % (date_from, date_to, val_id, date_from, date_to))


class HistoryViewer():
    """
    Bridge between the Web/REST interface and history/archive DB
    """

    def __init__(self, database):
        pass
