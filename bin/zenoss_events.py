import ta_zenoss_declare

import sys
import os
import os.path as op
from splunklib import modularinput as smi
from splunklib import client as client
from solnlib import log
from solnlib.modular_input import checkpointer
from zenoss_api import ZenossAPI
import xml.dom.minidom, xml.sax.saxutils
import re
import time
import json
import pytz
from datetime import datetime
from tzlocal import get_localzone
import calendar

# Date format for Zenoss API
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Clean checkpoint file once per day
CHECKPOINT_CLEAN_FREQUENCY = 1

# Number of events to process - Max 1000
LIMIT = 1000

# Time definitions
DAY = 86400
HOUR = 60

# App Name
APP_NAME = __file__.split(op.sep)[-3]

# Inherit Script class from splunklib
class ZenossModInput(smi.Script):

    # Get events from JSON api and process
    # Zenoss JSON API only sends 1000 events no matter how
    # high the limit is set. We have to page through results
    # 1000 events at a time and process them.
    # Params:
    #  z - ZenossAPI object
    #  events_dict - checkpoint file containing processed events
    #  ew - event writer object
    #  params - additional parameters for indexing closed & cleared events
    #  device - device to filter on
    #  start - record to start collecting from
    #  run_from - date to filter events on
    #  index_closed (boolean) - index closed events
    #  index_cleared (boolean) - index cleared events
    #  index_suppressed (boolean) - index suppressed events
    #  archive (boolean)- get archive history
    def get_and_process_events(self,
                           z,
                           events_dict,
                           ew,
                           params,
                           device,
                           start,
                           run_from,
                           index_closed,
                           index_cleared,
                           index_suppressed,
                           archive=False):
        if archive:
            events = z.get_events(device,
                                  start=start,
                                  archive=archive,
                                  last_time=run_from)
        else:
            events = z.get_events(device,
                                  start=start,
                                  last_time=run_from,
                                  closed=index_closed,
                                  cleared=index_cleared,
                                  suppressed=index_suppressed)
        if events['events']:
            start += LIMIT
            updated_events_dict = self.process_events(events, events_dict, ew, params)
            # Updating temporary collection of events data
            events_dict.update(updated_events_dict)

            self.get_and_process_events(z,
                                        events_dict,
                                        ew,
                                        params,
                                        device,
                                        start,
                                        run_from,
                                        index_closed,
                                        index_cleared,
                                        index_suppressed,
                                        archive)
        return events_dict

    # Write JSON event to stdout and Flush
    # Params:
    #  e - event
    def write_event(self, e, ew):
        #sys.stdout.write("%s\n" % json.dumps(e))
        #sys.stdout.flush()
        event = smi.Event(data=json.dumps(e))
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

            event_data = self.chk.get(evid)
            # Event hasn't been seen; add to checkpoint and index
            if event_data is None:
                # Event not seen yet
                self.write_event(e, ew)
                events_dict[evid] = dict(last_time=last_time, event_state=event_state, event_count=event_count)
                continue 

            # Load data stored in checkpoint for event with given evid
            event_dict = json.loads(event_data)

            # Get last timestamp and state from checkpoint
            last_event_ts = event_dict['last_time']
            last_event_state = event_dict['event_state']
            try:
                last_event_count = event_dict['event_count']
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
            self.logger.info(log_message)

        return events_dict

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
        return round(float(now_epoch - tstamp_epoch)/time_units,2)
    
    # Get password from Splunk storage password
    # params:
    #   realm - account realm
    #   account - username given to create an account
    #   session_key - auth token to access Splunk
    def get_password(self, realm, account, session_key):
        service = client.connect(token=session_key)
        storage_passwords = service.storage_passwords
        returned_credential = [k for k in storage_passwords if k.content.get('realm') == realm and k.content.get('username') == account]
        if len(returned_credential) < 1:
            raise Exception("No match found in storage password. Please verify given user and realm.")
        return returned_credential[0].content.get('clear_password')

    # Override get_scheme method
    # Define Scheme
    # params:
    #  none
    def get_scheme(self):
        scheme = smi.Scheme("Zenoss Events")
        scheme.description = "Modular input to pull events from Zenoss API"
        scheme.use_external_validation = True
        scheme.use_single_instance = False

        zenoss_username = smi.Argument("zenoss_username")
        zenoss_username.data_type = smi.Argument.data_type_string
        zenoss_username.required_on_edit = True
        zenoss_username.required_on_create = True
        scheme.add_argument(zenoss_username)

        zenoss_realm = smi.Argument("zenoss_realm") 
        zenoss_realm.data_type = smi.Argument.data_type_string
        zenoss_realm.required_on_edit = False
        zenoss_realm.required_on_create = False
        scheme.add_argument(zenoss_realm)

        zenoss_server = smi.Argument("zenoss_server")
        zenoss_server.data_type = smi.Argument.data_type_string
        zenoss_server.required_on_edit = True
        zenoss_server.required_on_create = True
        scheme.add_argument(zenoss_server)

        no_ssl_cert_check = smi.Argument("no_ssl_cert_check")
        no_ssl_cert_check.data_type = smi.Argument.data_type_boolean
        no_ssl_cert_check.required_on_edit = True
        no_ssl_cert_check.required_on_create = True
        scheme.add_argument(no_ssl_cert_check)

        cafile = smi.Argument("cafile")
        cafile.data_type = smi.Argument.data_type_string
        cafile.required_on_edit = False
        cafile.required_on_create = False
        scheme.add_argument(cafile)

        device = smi.Argument("device")
        device.data_type = smi.Argument.data_type_string
        device.required_on_edit = False
        device.required_on_create = False
        scheme.add_argument(device)

        tzone = smi.Argument("tzone")
        tzone.data_type = smi.Argument.data_type_string
        tzone.required_on_edit = False
        tzone.required_on_create = False
        scheme.add_argument(tzone)

        start_date = smi.Argument("start_date")
        start_date.data_type = smi.Argument.data_type_string
        start_date.required_on_edit = False
        start_date.required_on_create = False
        scheme.add_argument(start_date)

        index_closed = smi.Argument("index_closed")
        index_closed.data_type = smi.Argument.data_type_boolean
        index_closed.required_on_edit = False
        index_closed.required_on_create = False
        scheme.add_argument(index_closed)

        index_cleared = smi.Argument("index_cleared")
        index_cleared.data_type = smi.Argument.data_type_boolean
        index_cleared.required_on_edit = False
        index_cleared.required_on_create = False
        scheme.add_argument(index_cleared)

        index_archived = smi.Argument("index_archived")
        index_archived.data_type = smi.Argument.data_type_boolean
        index_archived.required_on_edit = False
        index_archived.required_on_create = False
        scheme.add_argument(index_archived)

        index_suppressed = smi.Argument("index_suppressed")
        index_suppressed.data_type = smi.Argument.data_type_boolean
        index_suppressed.required_on_edit = False
        index_suppressed.required_on_create = False
        scheme.add_argument(index_suppressed)

        index_repeats = smi.Argument("index_repeats")
        index_repeats.data_type = smi.Argument.data_type_boolean
        index_repeats.required_on_edit = False
        index_repeats.required_on_create = False
        scheme.add_argument(index_repeats)

        archive_threshold = smi.Argument("archive_threshold")
        archive_threshold.data_type = smi.Argument.data_type_string
        archive_threshold.required_on_edit = False
        archive_threshold.required_on_create = False
        scheme.add_argument(archive_threshold)

        checkpoint_delete_threshold = smi.Argument("checkpoint_delete_threshold")
        checkpoint_delete_threshold.data_type = smi.Argument.data_type_string
        checkpoint_delete_threshold.required_on_edit = False
        checkpoint_delete_threshold.required_on_create = False
        scheme.add_argument(checkpoint_delete_threshold)

        proxy_uri = smi.Argument("proxy_uri")
        proxy_uri.data_type = smi.Argument.data_type_string
        proxy_uri.required_on_edit = False
        proxy_uri.required_on_create = False
        scheme.add_argument(proxy_uri)

        proxy_username = smi.Argument("proxy_username")
        proxy_username.data_type = smi.Argument.data_type_string
        proxy_username.required_on_edit = False
        proxy_username.required_on_create = False
        scheme.add_argument(proxy_username)

        proxy_realm = smi.Argument("proxy_realm")
        proxy_realm.data_type = smi.Argument.data_type_string
        proxy_realm.required_on_edit = False
        proxy_realm.required_on_create = False
        scheme.add_argument(proxy_realm)
       
        return scheme 

    # Override validate_input method
    # Validate form input
    # params: None
    def validate_input(self, validation_definition):
        session_key = validation_definition.metadata["session_key"]
        username = validation_definition.parameters["zenoss_username"]
        zenoss_realm = validation_definition.parameters["zenoss_realm"]
        zenoss_server = validation_definition.parameters["zenoss_server"]
        no_ssl_cert_check = int(validation_definition.parameters["no_ssl_cert_check"])
        # Since Disable=1 and Enable=0, negate bool() to keep alignment
        ssl_cert_check = not bool(no_ssl_cert_check)
        cafile = validation_definition.parameters["cafile"]
        interval = validation_definition.parameters["interval"]
        start_date = validation_definition.parameters["start_date"]
        tz = validation_definition.parameters["tzone"]
        proxy_uri = validation_definition.parameters["proxy_uri"]
        proxy_username = validation_definition.parameters["proxy_username"]
        proxy_realm = validation_definition.parameters["proxy_realm"]
        proxy_password = None

        if int(interval) < 1:
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

        if proxy_uri is not None:
            p = re.compile("^(http|https):\/\/")
            if not (p.match(proxy_uri)):
                raise ValueError('Proxy URL does not match the correct format. Please verify URL begins with http:// or https://')
            
            if proxy_username is not None:
                # Proxy Authentication is optional.
                try:
                    proxy_password = self.get_password(proxy_realm, proxy_username, session_key)
                except Exception as e:
                    raise ValueError("Could not retrieve password for user {} and realm {} - {}".format(proxy_username, proxy_realm, e))

        # Get password from storage password
        try:
            password = self.get_password(zenoss_realm, username, session_key)
        except Exception as e:
            raise ValueError("Could not retrieve password for user {} and realm {} - {}".format(username, zenoss_realm, e))

        # Connect to Zenoss server and get an event to validate connection parameters are correct
        try:
            z = ZenossAPI(zenoss_server, username, password, proxy_uri, proxy_username, proxy_password, ssl_cert_check, cafile)
            events = z.get_events(None, start=0, limit=1)
        except Exception as e:
            raise ValueError("Failed to connect to {} and query for an event - {}".format(zenoss_server, e))

    # Override stream_events method
    # 
    # Johnny Walker neat, do it... do it!
    def stream_events(self, inputs, ew):
        input_items = {}
        input_name = list(inputs.inputs.keys())[0]
        input_items = inputs.inputs[input_name]

        # Create UTC timezone for conversion
        utc = pytz.utc
        params = {}
        start = 0

        zenoss_server = input_items.get("zenoss_server")
        username = input_items.get("zenoss_username")
        zenoss_realm = input_items.get("zenoss_realm")
        no_ssl_cert_check = int(input_items.get("no_ssl_cert_check"))
        # Since Disable=1 and Enable=0, negate bool() to keep alignment
        ssl_cert_check = not bool(no_ssl_cert_check)
        cafile = input_items.get("cafile")
        interval = int(input_items.get("interval", HOUR))
        start_date = input_items.get("start_date")
        index_closed = int(input_items.get("index_closed"))
        index_cleared = int(input_items.get("index_cleared"))
        index_archived = int(input_items.get("index_archived"))
        index_suppressed = int(input_items.get("index_suppressed"))
        index_repeats = int(input_items.get("index_repeats"))
        archive_threshold = int(input_items.get("archive_threshold"))
        checkpoint_delete_threshold = int(input_items.get("checkpoint_delete_threshold"))
        tzone = input_items.get("tzone")
        proxy_uri = input_items.get("proxy_uri")
        proxy_username = input_items.get("proxy_username")
        proxy_realm = input_items.get("proxy_realm")
        proxy_password = None

        meta_configs = self._input_definition.metadata

        # Generate logger with input name
        _, input_name = (input_name.split('//', 2))
        self.logger = log.Logs().get_logger('{}_input'.format(APP_NAME))

        # Log level configuration
        self.logger.setLevel('INFO')

        if index_closed: params = dict(index_closed=True)
        if index_cleared: params = dict(index_closed=True)
        if index_suppressed: params = dict(index_suppressed=True)
        if index_repeats: params = dict(index_repeats=True)

        try:
            if tzone:
                zenoss_tz = pytz.timezone(tzone)
            else:
                zenoss_tz = pytz.timezone(str(get_localzone()))
        except pytz.UnknownTimeZoneError as e:
            self.logger.warn("Unknown Timezone {} - Using default UTC".format(e))
            zenoss_tz = pytz.timezone("utc")
            
        # Get UTC timestamp
        utc_now = datetime.utcnow().replace(tzinfo=utc)
        # Convert to Zenoss server timezone
        now_local = utc_now.astimezone(zenoss_tz)
        # Create local time string
        now_str = now_local.strftime(DATE_FORMAT)

        # Load checkpoint file
        self.chk = checkpointer.FileCheckpointer(meta_configs['checkpoint_dir'])

        if self.chk.get("run_from") is None:
            # Initializing keys in checkpoint
            self.chk.update("run_from", start_date)
            self.chk.update("last_run", None)
            self.chk.update("last_cleaned", now_str)

        try:
            device = input_items.get("device")
        except Exception:
            device = None
        
        # Get password from storage password
        try:
            password = self.get_password(zenoss_realm, username, meta_configs['session_key'])
        except Exception as e:
            self.logger.error("Failed to get password for user %s, realm %s. Verify credential account exists. User who scheduled alert must have Admin privileges. - %s" % (username, zenoss_realm, e))
            sys.exit(1)
        
        if proxy_username is not None:
            try:
                proxy_password = self.get_password(proxy_realm, proxy_username, meta_configs['session_key'])
            except Exception as e:
                self.logger.error("Failed to get password for user %s, realm %s. Verify credential account exists. User who scheduled alert must have Admin privileges. - %s" % (proxy_username, proxy_realm, e))
                sys.exit(1)

        while True:
            run_from = self.chk.get("run_from")
            # When none --> get ALL events, otherwise from users' specified date

            # Work with datetimes in UTC and then convert to timezone of Zenoss server 
            utc_dt = utc.localize(datetime.utcnow())
            now_local = zenoss_tz.normalize(utc_dt.astimezone(zenoss_tz))
            now_epoch = calendar.timegm(now_local.utctimetuple())
            cur_time = now_local.strftime(DATE_FORMAT)
     
            # Connect to Zenoss web interface and get events
            try:
                z = ZenossAPI(zenoss_server, username, password, proxy_uri, proxy_username, proxy_password, ssl_cert_check, cafile)
            except Exception as e:
                log_message = "Zenoss Events: Failed to connect to server %s as user %s - Error: %s" % (zenoss_server,
                                                                                                        username,
                                                                                                        e)
                self.logger.error("{}. Exiting.".format(log_message))
                sys.exit(1)

            # Initializing data
            events_dict = {
                "run_from": self.chk.get("run_from"),
                "last_run": self.chk.get("last_run"),
                "last_cleaned": self.chk.get("last_cleaned")
            }

            # Get Events
            events_dict = self.get_and_process_events(z,
                                        events_dict,
                                        ew,
                                        params,
                                        device,
                                        start,
                                        run_from,
                                        index_closed,
                                        index_cleared,
                                        index_suppressed)

            # Update last run timestamp
            events_dict['last_run'] = cur_time

            # Processed archived events
            if index_archived:
                # Get last archive read, convert and create epoch timestamp
                try:
                    last_archive_read = self.chk.get('last_archive_read')
                    if last_archive_read is None:
                        # Key does not exist in checkpoint
                        raise Exception
                    archive_delta = self.calc_epoch_delta(last_archive_read, DATE_FORMAT, now_epoch, zenoss_tz, HOUR)
                except Exception:
                    last_archive_read = None
                    archive_delta = 0

                # Read the archived events table if it hasn't been read or
                # last read exceeds archive threshold 
                if archive_delta >= archive_threshold or \
                   not last_archive_read:
                    log_message = "Zenoss Events: Processing Archived Events\n" % params
                    self.logger.info(log_message)
                    self.get_and_process_events(z,
                                        events_dict,
                                        ew,
                                        params,
                                        device,
                                        start,
                                        run_from,
                                        index_closed,
                                        index_cleared,
                                        index_suppressed,
                                        archive=True)
                    events_dict['last_archive_read'] = cur_time

            # Clean checkpoint file
            try:
                last_cleaned = events_dict['last_cleaned']
                if last_cleaned is None:
                    # Key does not exist in checkpoint
                    raise Exception
            except Exception:
                last_cleaned = cur_time

            # Check to see if we need to clean the checkpoint file based on the 
            # checkpoint delta threshold
            last_cleaned_delta = self.calc_epoch_delta(last_cleaned, DATE_FORMAT, now_epoch, zenoss_tz, DAY)
            keys_toclean = []

            # Clean checkpoint file of old archive records
            if last_cleaned_delta >= CHECKPOINT_CLEAN_FREQUENCY:
                for k in events_dict.keys():
                    if isinstance(events_dict[k], dict) and 'last_time' in events_dict[k]:
                        last_time = events_dict[k]['last_time']
                        epoch_delta = self.calc_epoch_delta(last_time, "%Y-%m-%d %H:%M:%S", now_epoch, zenoss_tz, DAY)
                        if epoch_delta >= int(checkpoint_delete_threshold):
                            keys_toclean.append(k)
                            self.chk.delete(k)

            # Update checkpoint file
            for key in events_dict.keys():
                if key in keys_toclean:
                    continue
                # dict2str to save among checkpoints
                value = events_dict[key]
                if isinstance(value, dict):
                    value = json.dumps(value)
                self.chk.update(key, value)

            time.sleep(float(interval)) 

if __name__ == '__main__':
    exit_code = ZenossModInput().run(sys.argv)
    sys.exit(exit_code)
