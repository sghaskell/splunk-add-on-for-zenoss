import sys
import os
from splunklib.modularinput import *
from zenoss_api import ZenossAPI
from pprint import pprint
import xml.dom.minidom, xml.sax.saxutils
import re
import time
import json
import cPickle as pickle
import gzip
import pytz
from datetime import datetime
from tzlocal import get_localzone
import time
import calendar

# Date format for Zenoss API
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Clean checkpoint file once per day
CHECKPOINT_CLEAN_FREQUENCY = 1

# Time definitions
DAY = 86400
HOUR = 60

# Checkpoint file class
# params:
#  checkpoint_dir - directory where modinput writes checkpoint files
#  name - name of input to checkpoint
#  ew - EventWriter object for logging
class Checkpointer:
    def __init__(self, checkpoint_dir, name, ew):
        self.checkpoint_file_name = "%s/%s.pgz" % (checkpoint_dir, name)
        self.ew = ew

    @property
    # Method to load checkpoint file
    def load(self):
        f = self._open_checkpoint_file("rb")
        if f is None:
            return

        try:
            checkpoint_pickle = pickle.load(f)
            f.close()
            return checkpoint_pickle
        except Exception, e:
            log_message = "Error reading checkpoint pickle file '%s': %s" % (self.checkpoint_file_name, e)
            self.ew.write("ERROR", log_message)
            return {}

    # Method to open checkpoint file
    def _open_checkpoint_file(self, mode):
        if not os.path.exists(self.checkpoint_file_name):
            return None
        # try to open this file
        try:
            f = gzip.open(self.checkpoint_file_name, mode)
            return f
        except Exception, e:
            log_message = "Error opening '%s': %s" % (self.checkpoint_file_name, e)
            self.ew.log("ERROR", log_message)
            return None

    # Method to update checkpoint file
    def update(self, events_dict):
        tmp_file = "%s.tmp" % self.checkpoint_file_name

        try:
            f = gzip.open(tmp_file, "wb")
            pickle.dump(events_dict, f)
            f.close()
            os.remove(self.checkpoint_file_name)
            os.rename(tmp_file, self.checkpoint_file_name)
        except Exception, e:
            log_message = "Zenoss Events: Failed to update checkpoint file: %s" % e
            self.ew.log("ERROR", log_message)

    # Method to clean checkpoint file
    def clean(self, events_dict, checkpoint_delete_threshold, now_epoch, zenoss_tz):
        ts_format = "%Y-%m-%d %H:%M:%S"
        keys = events_dict.keys()
        for k in keys:
            if 'last_time' in events_dict[k]:
                last_time = events_dict[k]['last_time']
                epoch_delta = self.calc_epoch_delta(last_time, ts_format, now_epoch, zenoss_tz, DAY)
                if epoch_delta >= int(checkpoint_delete_threshold):
                    del events_dict[k]

# Inherit Script class from splunklib
class ZenossModInput(Script):

    # Write JSON event to stdout and Flush
    # Params:
    #  e - event
    def write_event(self, e, ew):
        #sys.stdout.write("%s\n" % json.dumps(e))
        #sys.stdout.flush()
        event = Event(data = json.dumps(e))
        ew.write_event(event)

    # Process Zenoss events
    # params:
    #  events - Events returned from Zenoss JSON API
    #  events_dict - checkpoint file containing processed events
    #  params - additional parameters for indexing closed & cleared events
    def process_events(self, events, events_dict, ew, params=None):
        for e in events['events']:
            evid = str(e['evid'])
            last_time = str(e['lastTime'])
            first_time = str(e['firstTime'])
            state_change = str(e['stateChange'])
            event_state = str(e['eventState'])
            event_count = int(e['count'])

            # Event hasn't been seen; add to checkpoint and index
            if evid not in events_dict:
                # Event not seen yet
                self.write_event(e, ew)
                events_dict[evid] = dict(last_time=last_time, event_state=event_state, event_count=event_count)
                continue 

            # Get last timestamp and state from checkpoint
            last_event_ts = events_dict[evid]['last_time']
            last_event_state = events_dict[evid]['event_state']
            try:
                last_event_count = events_dict[evid]['event_count']
            except Exception:
                last_event_count = event_count

            # index if count is greater than last count
            if 'index_repeats' in params \
               and event_count > last_event_count:
                self.write_event(e, ew)
                events_dict[evid] = dict(last_time=last_time, event_state=event_state, event_count=event_count)
                continue

            if (last_time == first_time or last_time == state_change) and \
               last_time != last_event_ts:
                self.write_event(e, ew)
                events_dict[evid] = dict(last_time=last_time, event_state=event_state, event_count=event_count)
                continue

            # Check for cleared, closed or re-opened events
            if params and \
               event_state != last_event_state:
                self.write_event(e, ew)
                events_dict[evid] = dict(last_time=last_time, event_state=event_state, event_count=event_count)
                continue

            # Event is unchanged - log info
            log_message = "Zenoss Events: EventID %s present and unchanged since \
lastTime %s -- skipping" % (evid, last_time)
            ew.log("INFO", log_message)

    # Calculate epoch time delta
    # params:
    #  tstamp - timestamp
    #  format - strptime format of timestamp
    #  now_epoch - local epoch
    #  zenoss_tz - pytz timezone of Zenoss server
    #  time_units - divisor (minutes, seconds, hours) for float
    def calc_epoch_delta(self, tstamp, format, now_epoch, zenoss_tz, time_units):
        tstamp_dt = datetime.strptime(tstamp, format)
        tstamp_local = zenoss_tz.localize(tstamp_dt)
        tstamp_epoch = calendar.timegm(tstamp_local.utctimetuple())
        epoch_delta = round(float(now_epoch - tstamp_epoch)/time_units,2)
        return(epoch_delta)

    # Override get_scheme method
    # Define Scheme
    # params:
    #  none
    def get_scheme(self):
        scheme = Scheme("Zenoss Events")
        scheme.description = "Modular input to pull events from Zenoss API"
        scheme.use_external_validation = True
        scheme.use_single_instance = False

        username = Argument("username")
        username.data_type = Argument.data_type_string
        username.required_on_edit = True
        username.required_on_create = True
        scheme.add_argument(username)

        password = Argument("password") 
        password.data_type = Argument.data_type_string
        password.required_on_edit = True
        password.required_on_create = True
        scheme.add_argument(password)

        zenoss_server = Argument("zenoss_server")
        zenoss_server.data_type = Argument.data_type_string
        zenoss_server.required_on_edit = True
        zenoss_server.required_on_create = True
        scheme.add_argument(zenoss_server)

        device = Argument("device")
        device.data_type = Argument.data_type_string
        device.required_on_edit = False
        device.required_on_create = False
        scheme.add_argument(device)

        tzone = Argument("tzone")
        tzone.data_type = Argument.data_type_string
        tzone.required_on_edit = False
        tzone.required_on_create = False
        scheme.add_argument(tzone)

        start_date = Argument("start_date")
        start_date.data_type = Argument.data_type_string
        start_date.required_on_edit = False
        start_date.required_on_create = False
        scheme.add_argument(start_date)

        index_closed = Argument("index_closed")
        index_closed.data_type = Argument.data_type_boolean
        index_closed.required_on_edit = False
        index_closed.required_on_create = False
        scheme.add_argument(index_closed)

        index_cleared = Argument("index_cleared")
        index_cleared.data_type = Argument.data_type_boolean
        index_cleared.required_on_edit = False
        index_cleared.required_on_create = False
        scheme.add_argument(index_cleared)

        index_archived = Argument("index_archived")
        index_archived.data_type = Argument.data_type_boolean
        index_archived.required_on_edit = False
        index_archived.required_on_create = False
        scheme.add_argument(index_archived)

        index_suppressed = Argument("index_suppressed")
        index_suppressed.data_type = Argument.data_type_boolean
        index_suppressed.required_on_edit = False
        index_suppressed.required_on_create = False
        scheme.add_argument(index_suppressed)

        index_repeats = Argument("index_repeats")
        index_repeats.data_type = Argument.data_type_boolean
        index_repeats.required_on_edit = False
        index_repeats.required_on_create = False
        scheme.add_argument(index_repeats)

        archive_threshold = Argument("archive_threshold")
        archive_threshold.data_type = Argument.data_type_string
        archive_threshold.required_on_edit = False
        archive_threshold.required_on_create = False
        scheme.add_argument(archive_threshold)

        checkpoint_delete_threshold = Argument("checkpoint_delete_threshold")
        checkpoint_delete_threshold.data_type = Argument.data_type_string
        checkpoint_delete_threshold.required_on_edit = False
        checkpoint_delete_threshold.required_on_create = False
        scheme.add_argument(checkpoint_delete_threshold)
       
        return scheme 

    # Override validate_input method
    # Validate form input
    # params: None
    def validate_input(self, validation_definition):
        username = validation_definition.parameters["username"]
        password = validation_definition.parameters["password"]
        zenoss_server = validation_definition.parameters["zenoss_server"]
        interval = validation_definition.parameters["interval"]
        start_date = validation_definition.parameters["start_date"]
        tz = validation_definition.parameters["tzone"]

        if not username:
            raise ValueError("Please specify valid username")

        if not zenoss_server:
            raise ValueError("Please specify Zenoss web interface")

        if not interval is None and int(interval) < 1:
            raise ValueError("Interval value must be a non-zero positive integer")

        if start_date is not None:
            p = re.compile("\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
            result = p.match(start_date)
            if not result:
                raise ValueError('Date does not match the correct format: %Y-%m-%dT%H:%M:%S; \
example: 2015-03-16T00:00:00')

        # Validate timezone exists in pytz database
        if tz is not None and tz not in pytz.all_timezones:
            raise ValueError("Invalid timezone - See http://en.wikipedia.org/wiki/List_of_tz_database_time_zones \
for reference")

        # Connect to Zenoss server and get an event to validate connection parameters are correct
        try:
            z = ZenossAPI(zenoss_server, username, password)
            events = z.get_events(None, start=0, limit=1)
        except:
            raise ValueError("Failed to connect to %s and query for an event - Verify username, password and web \
interface address are correct" % zenoss_server)

    # Override stream_events method
    # 
    # Johnny Walker neat, do it... do it!
    def stream_events(self, inputs, ew):
        instance = inputs.inputs.keys().pop()
        config = inputs.inputs[instance]
        input_name = re.sub("^.*?\/\/","", instance) 
                
        # Create UTC timezone for conversion
        utc = pytz.utc
        params = {}
        start = 0
        #config = get_input_config()

        zenoss_server = config.get("zenoss_server")
        username = config.get("username")
        password = config.get("password")
        interval = int(config.get("interval", HOUR))
        start_date = config.get("start_date")
        index_closed = int(config.get("index_closed"))
        index_cleared = int(config.get("index_cleared"))
        index_archived = int(config.get("index_archived"))
        index_suppressed = int(config.get("index_suppressed"))
        index_repeats = int(config.get("index_repeats"))
        archive_threshold = int(config.get("archive_threshold"))
        checkpoint_delete_threshold = int(config.get("checkpoint_delete_threshold"))
        tzone = config.get("tzone")

        if index_closed: params = dict(index_closed=True)
        if index_cleared: params = dict(index_closed=True)
        if index_suppressed: params = dict(index_suppressed=True)
        if index_repeats: params = dict(index_repeats=True)

        if tzone:
            zenoss_tz = pytz.timezone(tzone)
        else:
            zenoss_tz = pytz.timezone(str(get_localzone()))
            

        # Load checkpoint file
        chk = Checkpointer(str(inputs.metadata.get("checkpoint_dir")), str(input_name), ew)
        events_dict = chk.load

        if not events_dict:
            # Get UTC timestamp
            utc_now = datetime.utcnow().replace(tzinfo=utc)
            # Convert to Zenoss server timezone
            now_local = utc_now.astimezone(zenoss_tz)
            # Create local time string
            now_str = now_local.strftime(DATE_FORMAT)
            
            if start_date:
                events_dict = dict(run_from=start_date, last_run=None, last_cleaned=now_str)
            else:
                events_dict = dict(run_from=None, last_run=None, last_cleaned=now_str)
            # Create checkpoint file
            try:
                gzip.open(chk.checkpoint_file_name, 'wb').close()
                chk.update(events_dict)
            except Exception, e:
                log_message = "Zenoss Events: Failed to create checkpoint file %s - Error: %s" % (chk.checkpoint_file_name, e)
                ew.log("ERROR", log_message)
        try:
            device = config.get("device")
        except Exception:
            device = None

        while True:
            # Load checkpoint file
            chk = Checkpointer(str(inputs.metadata.get("checkpoint_dir")), str(input_name), ew)
            events_dict = chk.load
            run_from = events_dict.get("run_from")

            if not run_from: run_from = start_date
       
            # Work with datetimes in UTC and then convert to timezone of Zenoss server 
            utc_dt = utc.localize(datetime.utcnow())
            now_local = zenoss_tz.normalize(utc_dt.astimezone(zenoss_tz))
            now_epoch = calendar.timegm(now_local.utctimetuple())
            cur_time = now_local.strftime(DATE_FORMAT)
     
            # Connect to Zenoss web interface and get events
            try:
                z = ZenossAPI(zenoss_server, username, password)
            except Exception, e:
                log_message = "Zenoss Events: Failed to connect to server %s as user %s - Error: %s" % (zenoss_server,
                                                                                                        username,
                                                                                                        e)
                ew.log("ERROR", log_message)
                sys.exit(1)

            # Get Events
            events = z.get_events(device, start=start, last_time=run_from, closed=index_closed, cleared=index_cleared, suppressed=index_suppressed)
            self.process_events(events, events_dict, ew, params)

            # Update last run timestamp
            events_dict['last_run'] = cur_time

            # Processed archived events
            if index_archived:
                # Get last archive read, convert and create epoch timestamp
                try:
                    last_archive_read = events_dict['last_archive_read']
                    archive_delta = self.calc_epoch_delta(last_archive_read, DATE_FORMAT, now_epoch, zenoss_tz, HOUR)
                except Exception:
                    last_archive_read = None
                    archive_delta = 0

                # Read the archived events table if it hasn't been read or
                # last read exceeds archive threshold 
                if archive_delta >= archive_threshold or \
                   not last_archive_read:
                    log_message = "Zenoss Events: Processing Archived Events\n" % params
                    ew.log("ERROR", log_message)
                    archive_events = z.get_events(device, start=start, archive=True, last_time=run_from)
                    self.process_events(archive_events, events_dict, ew, params)
                    events_dict['last_archive_read'] = cur_time

            # Clean checkpoint file
            try:
                last_cleaned = events_dict['last_cleaned']
            except Exception:
                last_cleaned = cur_time

            # Check to see if we need to clean the checkpoint file based on the 
            # checkpoint delta threshold
            last_cleaned_delta = self.calc_epoch_delta(last_cleaned, DATE_FORMAT, now_epoch, zenoss_tz, DAY)

            # Clean checkpoint file of old archive records
            if last_cleaned_delta >= CHECKPOINT_CLEAN_FREQUENCY:
                chk.clean(events_dict, checkpoint_delete_threshold, now_epoch, zenoss_tz)

            # Update checkpoint file
            chk.update(events_dict)

            time.sleep(float(interval)) 

if __name__ == '__main__':
    sys.exit(ZenossModInput().run(sys.argv))    
