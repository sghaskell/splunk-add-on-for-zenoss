
# encoding = utf-8
import untangle 
import sys
import os
import argparse
import gzip
import csv
from pprint import pprint
from zenoss_server_config import ZenossServerConfig
from zenoss_api import ZenossAPI


def process_event(helper, *args, **kwargs):
    """
    # IMPORTANT
    # Do not remove the anchor macro:start and macro:end lines.
    # These lines are used to generate sample code. If they are
    # removed, the sample code will not be updated when configurations
    # are updated.

    [sample_code_macro:start]

    # The following example gets the alert action parameters and prints them to the log
    web_address = helper.get_param("web_address")
    helper.log_info("web_address={}".format(web_address))

    splunk_server_name = helper.get_param("splunk_server_name")
    helper.log_info("splunk_server_name={}".format(splunk_server_name))

    credential_account = helper.get_param("credential_account")
    helper.log_info("credential_account={}".format(credential_account))

    credential_app_context = helper.get_param("credential_app_context")
    helper.log_info("credential_app_context={}".format(credential_app_context))

    credential_realm = helper.get_param("credential_realm")
    helper.log_info("credential_realm={}".format(credential_realm))

    no_ssl_cert_check = helper.get_param("no_ssl_cert_check")
    helper.log_info("no_ssl_cert_check={}".format(no_ssl_cert_check))

    cafile = helper.get_param("cafile")
    helper.log_info("cafile={}".format(cafile))


    # The following example adds two sample events ("hello", "world")
    # and writes them to Splunk
    # NOTE: Call helper.writeevents() only once after all events
    # have been added
    helper.addevent("hello", sourcetype="sample_sourcetype")
    helper.addevent("world", sourcetype="sample_sourcetype")
    helper.writeevents(index="summary", host="localhost", source="localhost")

    # The following example gets the events that trigger the alert
    events = helper.get_events()
    for event in events:
        helper.log_info("event={}".format(event))

    # helper.settings is a dict that includes environment configuration
    # Example usage: helper.settings["server_uri"]
    helper.log_info("server_uri={}".format(helper.settings["server_uri"]))
    [sample_code_macro:end]
    """

    helper.log_info("Alert action zenoss_event started.")

    web_address = helper.get_param("web_address")
    credential_account = helper.get_param("credential_account")
    credential_realm = helper.get_param("credential_realm")
    results_file = helper.get_param("results_file")
    no_ssl_cert_check = helper.get_param("no_ssl_cert_check")
    cafile = helper.get_param("cafile")
    credential_app_context = helper.get_param("credential_app_context")
    session_key = helper.session_key
    splunk_server_name = helper.get_param("splunk_server_name")

    try:
        # Get password from REST API
        res = helper.send_http_request("https://%s:8089/servicesNS/admin/%s/storage/passwords/%s:%s" % (splunk_server_name, credential_app_context, credential_realm, credential_account), "GET", headers={'Authorization': 'Splunk %s' % session_key}, verify=False)

        # Parse clear password
        user_xml = untangle.parse(res.content)
        for o in user_xml.feed.entry.content.s_dict.s_key:
            if(o['name'] == 'clear_password'):
                password = o.cdata
    except Exception, e:
        helper.log_error("Failed to get password for user %s, realm %s. Verify credential account exists. User who scheduled alert must have Admin privileges. - %s" % (credential_account, credential_realm, e))
        sys.exit(1)

    try:
        z = ZenossAPI(web_address, credential_account, password, bool(int(no_ssl_cert_check)), cafile)
    except Exception, e:
        helper.log_error("Failed to connect to zenoss server - %s" % e)
        sys.exit(1)

    events = helper.get_events()

    for r in events:
        helper.log_info("event={}".format(r))
    
        if r.has_key('device'):
            device = r.get('device')
        elif r.has_key('host'):
            device = r.get('host')
        else:
            helper.log_error("No host or device specified")
            sys.exit(1)

        if r.has_key('component'):
            component = r.get('component')
        else:
            component = ''

        if r.has_key('evclass'):
            evclass = r.get('evclass')
        else:
            evclass = ''

        if r.has_key('evclasskey'):
            evclasskey = r.get('evclasskey')
        else:
            evclasskey = ''
        helper.log_info("%s %s %s" % (device, evclass, component))
        try:
            z.create_event_on_device(device, r.get('severity'), r.get('summary'), component=component, evclass=evclass, evclasskey=evclasskey)
        except Exception, e:
            helper.log_error("Zenoss Create Event: Failed to create event - %s" % e)
            sys.exit(1)        
    
    # TODO: Implement your alert action logic here
    return 0
