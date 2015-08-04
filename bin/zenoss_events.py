import sys
import os
from zenoss_api import ZenossAPI
from pprint import pprint
import logging
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

#set up logging
logging.root.setLevel(logging.ERROR)
#logging.root.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s %(message)s')
#with zero args , should go to STD ERR
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logging.root.addHandler(handler)

# Date format for Zenoss API
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Clean checkpoint file once per day
CHECKPOINT_CLEAN_FREQUENCY = 1

# Time definitions
DAY = 86400
HOUR = 60

SCHEME = """<scheme>
   <title>Zenoss</title>
   <description>Modular input to pull events from Zenoss API</description>
   <use_external_validation>true</use_external_validation>
   <use_single_instance>false</use_single_instance>
   <streaming_mode>simple</streaming_mode>

   <endpoint>
     <args>
       <arg name="username">
         <data_type>string</data_type>
         <required_on_edit>true</required_on_edit>
         <required_on_create>true</required_on_create>
       </arg>
       <arg name="password">
         <data_type>string</data_type>
         <required_on_edit>true</required_on_edit>
         <required_on_create>true</required_on_create>
       </arg>
       <arg name="zenoss_server">
         <data_type>string</data_type>
         <required_on_edit>true</required_on_edit>
         <required_on_create>true</required_on_create>
       </arg>
       <arg name="device">
         <data_type>string</data_type>
         <required_on_edit>false</required_on_edit>
         <required_on_create>false</required_on_create>
       </arg>
       <arg name="tzone">
         <data_type>string</data_type>
         <required_on_edit>false</required_on_edit>
         <required_on_create>false</required_on_create>
       </arg>
       <arg name="start_date">
         <data_type>string</data_type>
         <required_on_edit>false</required_on_edit>
         <required_on_create>false</required_on_create>
       </arg>
       <arg name="index_closed">
         <data_type>boolean</data_type>
         <required_on_edit>false</required_on_edit>
         <required_on_create>false</required_on_create>
       </arg>
       <arg name="index_cleared">
         <data_type>boolean</data_type>
         <required_on_edit>false</required_on_edit>
         <required_on_create>false</required_on_create>
       </arg>
       <arg name="index_archived">
         <data_type>boolean</data_type>
         <required_on_edit>false</required_on_edit>
         <required_on_create>false</required_on_create>
       </arg>
       <arg name="index_suppressed">
         <data_type>boolean</data_type>
         <required_on_edit>false</required_on_edit>
         <required_on_create>false</required_on_create>
       </arg>
       <arg name="index_repeats">
         <data_type>boolean</data_type>
         <required_on_edit>false</required_on_edit>
         <required_on_create>false</required_on_create>
       </arg>
       <arg name="archive_threshold">
         <data_type>string</data_type>
         <required_on_edit>false</required_on_edit>
         <required_on_create>false</required_on_create>
       </arg>
       <arg name="checkpoint_delete_threshold">
         <data_type>string</data_type>
         <required_on_edit>false</required_on_edit>
         <required_on_create>false</required_on_create>
       </arg>
     </args>
   </endpoint>
</scheme>
"""

# Checkpoint file class
class Checkpointer:
    def __init__(self, checkpoint_dir, name):
        m = re.search(r'\/\/(.*)$', name)
        self.checkpoint_file_name = "%s/%s.pgz" % (checkpoint_dir, m.group(1))

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
            logging.error("Error reading checkpoint pickle file '%s': %s" % (self.checkpoint_file_name, e))
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
            logging.error("Error opening '%s': %s" % (self.checkpoint_file_name, e))
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
            logging.error("Zenoss Events: Failed to update checkpoint file: %s" % e)

    # Method to clean checkpoint file
    def clean(self, events_dict, checkpoint_delete_threshold, now_epoch, zenoss_tz):
        ts_format = "%Y-%m-%d %H:%M:%S"
        keys = events_dict.keys()
        for k in keys:
            if 'last_time' in events_dict[k]:
                last_time = events_dict[k]['last_time']
                epoch_delta = calc_epoch_delta(last_time, ts_format, now_epoch, zenoss_tz, DAY)
                if epoch_delta >= int(checkpoint_delete_threshold):
                    del events_dict[k]

def usage():
    print "usage: %s [--scheme|--validate-arguments]"
    logging.error("Incorrect Program Usage")
    sys.exit(2)

def get_validation_data():
    val_data = {}

    # read everything from stdin
    val_str = sys.stdin.read()

    # parse the validation XML
    doc = xml.dom.minidom.parseString(val_str)
    root = doc.documentElement

    logging.debug("XML: found items")
    item_node = root.getElementsByTagName("item")[0]
    if item_node:
        logging.debug("XML: found item")

        name = item_node.getAttribute("name")
        val_data["stanza"] = name

        params_node = item_node.getElementsByTagName("param")
        for param in params_node:
            name = param.getAttribute("name")
            logging.debug("Found param %s" % name)
            if name and param.firstChild and \
               param.firstChild.nodeType == param.firstChild.TEXT_NODE:
                val_data[name] = param.firstChild.data

    return val_data

#read XML configuration passed from splunkd, need to refactor to support single instance mode
def get_validation_config():
    val_data = {}

    # read everything from stdin
    val_str = sys.stdin.read()

    # parse the validation XML
    doc = xml.dom.minidom.parseString(val_str)
    root = doc.documentElement

    logging.debug("XML: found items")
    item_node = root.getElementsByTagName("item")[0]
    if item_node:
        logging.debug("XML: found item")

        name = item_node.getAttribute("name")
        val_data["stanza"] = name

        params_node = item_node.getElementsByTagName("param")
        for param in params_node:
            name = param.getAttribute("name")
            logging.debug("Found param %s" % name)
            if name and param.firstChild and \
               param.firstChild.nodeType == param.firstChild.TEXT_NODE:
                val_data[name] = param.firstChild.data

    return val_data

# Print error message to Splunk
# params:
#  s - error string
def print_validation_error(s):
    print "<error><message>%s</message></error>" % xml.sax.saxutils.escape(s)

# Validate form input
# params: None
def do_validate():

    try:
        config = get_validation_config()

        username = config.get("username")
        password = config.get("password")
        zenoss_server = config.get("zenoss_server")
        interval = config.get("interval")
        start_date = config.get("start_date")
        tz = config.get("tz")


        validation_failed = False

        if not username:
            print_validation_error("Please specify valid username")
            validation_failed = True

        if not zenoss_server:
            print_validation_error("Please specify Zenoss web interface")
            validation_failed = True

        if not interval is None and int(interval) < 1:
            print_validation_error("Interval value must be a positive integer")
            validation_failed = True

        if start_date is not None:
            p = re.compile("\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
            result = p.match(start_date)
            if not result:
                print_validation_error('Date does not match the correct format: %Y-%m-%dT%H:%M:%S; \
example: 2015-03-16T00:00:00')
                validation_failed = True

        if tz is not None and tz not in pytz.all_timezones:
            print_validation_error("Invalid timezone - See http://en.wikipedia.org/wiki/List_of_tz_database_time_zones \
for reference")
            validation_failed = True

        # Connect to Zenoss server and get an event to validate connection parameters are correct
        try:
            z = ZenossAPI(zenoss_server, username, password)
            events = z.get_events(None, start=0, limit=1)
        except ValueError, e:
            failure_string = "Failed to connect to %s and query for an event - Check username, password and web \
interface address are correct" % zenoss_server
            print_validation_error(failure_string)
            validation_failed = True

        if validation_failed:
            sys.exit(2)

    except RuntimeError,e:
        logging.error("Looks like an error: %s" % str(e))
        sys.exit(1)

#read XML configuration passed from splunkd, need to refactor to support single instance mode
def get_input_config():
    config = {}

    try:
        # read everything from stdin
        config_str = sys.stdin.read()

        # parse the config XML
        doc = xml.dom.minidom.parseString(config_str)
        root = doc.documentElement
        conf_node = root.getElementsByTagName("configuration")[0]
        if conf_node:
            logging.debug("XML: found configuration")
            stanza = conf_node.getElementsByTagName("stanza")[0]
            if stanza:
                stanza_name = stanza.getAttribute("name")
                if stanza_name:
                    logging.debug("XML: found stanza " + stanza_name)
                    config["name"] = stanza_name

                    params = stanza.getElementsByTagName("param")
                    for param in params:
                        param_name = param.getAttribute("name")
                        logging.debug("XML: found param '%s'" % param_name)
                        if param_name and param.firstChild and \
                           param.firstChild.nodeType == param.firstChild.TEXT_NODE:
                            data = param.firstChild.data
                            config[param_name] = data
                            logging.debug("XML: '%s' -> '%s'" % (param_name, data))

        checkpnt_node = root.getElementsByTagName("checkpoint_dir")[0]
        if checkpnt_node and checkpnt_node.firstChild and \
           checkpnt_node.firstChild.nodeType == checkpnt_node.firstChild.TEXT_NODE:
            config["checkpoint_dir"] = checkpnt_node.firstChild.data

        if not config:
            raise Exception, "Invalid configuration received from Splunk."


    except Exception, e:
        raise Exception, "Error getting Splunk configuration via STDIN: %s" % str(e)

    return config

# Write JSON event to stdout and Flush
# Params:
#  e - event
def write_event(e):
    sys.stdout.write("%s\n" % json.dumps(e))
    sys.stdout.flush()

# Process Zenoss events
# params:
#  events - Events returned from Zenoss JSON API
#  events_dict - checkpoint file containing processed events
#  params - additional parameters for indexing closed & cleared events
def process_events(events, events_dict, params=None):
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
            write_event(e)
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
            write_event(e)
            events_dict[evid] = dict(last_time=last_time, event_state=event_state, event_count=event_count)
            continue

        if (last_time == first_time or last_time == state_change) and \
           last_time != last_event_ts:
            write_event(e)
            events_dict[evid] = dict(last_time=last_time, event_state=event_state, event_count=event_count)
            continue

        # Check for cleared, closed or re-opened events
        if params and \
           event_state != last_event_state:
            write_event(e)
            events_dict[evid] = dict(last_time=last_time, event_state=event_state, event_count=event_count)
            continue

        # Event is unchanged - log info
        logging.info("Zenoss Events: EventID %s present and unchanged since lastTime %s -- skipping" % (evid,
                                                                                                        last_time))

def do_scheme():
    print SCHEME

# Calculate epoch time delta
# params:
#  tstamp - timestamp
#  format - strptime format of timestamp
#  now_epoch - local epoch
#  zenoss_tz - pytz timezone of Zenoss server
#  time_units - divisor (minutes, seconds, hours) for float
def calc_epoch_delta(tstamp, format, now_epoch, zenoss_tz, time_units):
    tstamp_dt = datetime.strptime(tstamp, format)
    tstamp_local = zenoss_tz.localize(tstamp_dt)
    tstamp_epoch = calendar.timegm(tstamp_local.utctimetuple())
    epoch_delta = round(float(now_epoch - tstamp_epoch)/time_units,2)
    return(epoch_delta)

def run():
    # Create UTC timezone for conversion
    utc = pytz.utc
    params = {}
    start = 0
    config = get_input_config()

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
    chk = Checkpointer(str(config["checkpoint_dir"]), str(config["name"]))
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
            logging.error("Zenoss Events: Failed to create checkpoint file %s - Error: %s" % (chk.checkpoint_file_name,
                                                                                              e))

    try:
        device = config.get("device")
    except Exception:
        device = None

    while True:
        # Load checkpoint file
        chk = Checkpointer(str(config["checkpoint_dir"]), str(config["name"]))
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
            logging.error("Zenoss Events: Failed to connect to server %s as user %s - Error: %s" % (zenoss_server,
                                                                                                    username,
                                                                                                    e))
            sys.exit(1)

        # Get Events
        events = z.get_events(device, start=start, last_time=run_from, closed=index_closed, cleared=index_cleared, suppressed=index_suppressed)
        process_events(events, events_dict, params)

        # Update last run timestamp
        events_dict['last_run'] = cur_time

        # Processed archived events
        if index_archived:
            # Get last archive read, convert and create epoch timestamp
            try:
                last_archive_read = events_dict['last_archive_read']
                archive_delta = calc_epoch_delta(last_archive_read, DATE_FORMAT, now_epoch, zenoss_tz, HOUR)
            except Exception:
                last_archive_read = None
                archive_delta = 0

            # Read the archived events table if it hasn't been read or
            # last read exceeds archive threshold 
            if archive_delta >= archive_threshold or \
               not last_archive_read:
                logging.error("Zenoss Events: Processing Archived Events\n" % params)
                archive_events = z.get_events(device, start=start, archive=True, last_time=run_from)
                process_events(archive_events, events_dict, params)
                events_dict['last_archive_read'] = cur_time

        # Clean checkpoint file
        try:
            last_cleaned = events_dict['last_cleaned']
        except Exception:
            last_cleaned = cur_time

        # Check to see if we need to clean the checkpoint file based on the 
        # checkpoint delta threshold
        last_cleaned_delta = calc_epoch_delta(last_cleaned, DATE_FORMAT, now_epoch, zenoss_tz, DAY)

        # Clean checkpoint file of old archive records
        if last_cleaned_delta >= CHECKPOINT_CLEAN_FREQUENCY:
            chk.clean(events_dict, checkpoint_delete_threshold, now_epoch, zenoss_tz)

        # Update checkpoint file
        chk.update(events_dict)

        time.sleep(float(interval)) 

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == "--scheme":
            do_scheme()
        elif sys.argv[1] == "--validate-arguments":
            do_validate()
        else:
            usage()
    else:
        # Get Zenoss Events
        run()

    sys.exit(0)
