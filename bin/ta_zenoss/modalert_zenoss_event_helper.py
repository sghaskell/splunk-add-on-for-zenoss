
# encoding = utf-8
import sys
import os
import splunklib.client as client
from zenoss_api import ZenossAPI

def get_password(helper, realm, account):
    helper.log_debug("Retrieving password for account '{}' at realm '{}'".format(account, realm))

    try:
        service = client.connect(token=helper.session_key)
        storage_passwords = service.storage_passwords
        returned_credential = [k for k in storage_passwords if k.content.get('realm') == realm and k.content.get('username') == account]
        if len(returned_credential) < 1:
            raise Exception("Combination of user and realm not found in storage password")
        return returned_credential[0].content.get('clear_password')
    except Exception as e:
        helper.log_error("Failed to get password for user %s, realm %s. Verify credential account exists. User who scheduled alert must have Admin privileges. - %s" % (account, realm, e))
        sys.exit(1)

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
    no_ssl_cert_check = int(helper.get_param("no_ssl_cert_check"))
    # Since Disable=1 and Enable=0, negate bool() to keep alignment
    ssl_cert_check = not bool(no_ssl_cert_check)
    cafile = helper.get_param("cafile")

    proxy_uri = helper.get_param("proxy_uri")
    proxy_credential_account = helper.get_param("proxy_credential_account")
    proxy_credential_realm = helper.get_param("proxy_credential_realm")
    proxy_password = None

    password = get_password(helper, credential_realm, credential_account)
    if proxy_credential_account and proxy_credential_realm:
        helper.log_info("Proxy with credentials configured")
        proxy_password = get_password(helper, proxy_credential_realm, proxy_credential_account)

    try:
        z = ZenossAPI(web_address, credential_account, password, proxy_uri, 
            proxy_credential_account, proxy_password, ssl_cert_check, cafile)
    except Exception as e:
        helper.log_error("Failed to connect to zenoss server - %s" % e)
        sys.exit(1)

    events = helper.get_events()

    for r in events:
        helper.log_info("event={}".format(r))
    
        if "device" in r.keys():
            device = r.get('device')
        elif "host" in r.keys():
            device = r.get('host')
        else:
            helper.log_error("No host or device specified in event")
            sys.exit(1)

        component = "" if not "component" in r.keys() else r.get("component")
        evclass = "" if not "evclass" in r.keys() else r.get("evclass")
        evclass_key = "" if not "evclasskey" in r.keys() else r.get("evclasskey")
        
        helper.log_info("{} {} {}".format(device, evclass, component))
        
        try:
            z.create_event_on_device(device, r.get('severity'), r.get('summary'), component=component, evclass=evclass, evclasskey=evclass_key)
        except Exception as e:
            helper.log_error("Zenoss Create Event: Failed to create event - {}".format(e))
            sys.exit(1)   
    
    return 0