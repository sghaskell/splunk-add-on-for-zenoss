# Author: Scott Haskell
# Company: Splunk Inc.
# Date: 2015-05-13
# Description:
#  Script to create an alert in Zenoss
#
# Arguments:
#  stanza in local/zenoss_servers.conf
#  file containing search results
#    expected fields in file: 
#      "device" OR "host" - device/host name
#      "severity" - severity of alert "Critical","Error","Warning","Info","Debug","Clear"
#      "summary" - Plain text summary of the event
# 
import sys
import os
import argparse
import gzip
import csv
import logging
from pprint import pprint
from zenoss_server_config import ZenossServerConfig
from zenoss_api import ZenossAPI

#set up logging
logging.root.setLevel(logging.ERROR)
#logging.root.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s %(message)s')
#with zero args , should go to STD ERR
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logging.root.addHandler(handler)

def parse_args():
    argparser = argparse.ArgumentParser(description='Create Zenoss Event')
    argparser.add_argument('-s', '--stanza', required=True,
                            help='stanza')
    argparser.add_argument('-f', '--file', required=True,
                            help='results file')
    flags = argparser.parse_args()

    return flags

def main():
    flags = parse_args()
    config = ZenossServerConfig(flags.stanza)
    
    try:
        z = ZenossAPI(config.web_address, config.username, config.password)
    except Exception, e:
        logging.error("Zenoss Create Event: Failed to connect to zenoss server - %s" % e)

    with gzip.open(flags.file, 'rb') as csvfile:
        results = csv.DictReader(csvfile)
        for r in results:
            if r.has_key('device'):
                device = r.get('device')
            elif r.has_key('host'): 
                device = r.get('host')
            else:
                logging.error("Zenoss Create Event: No host or device specified")
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
                
            try:
                z.create_event_on_device(device, r.get('severity'), r.get('summary'), component=component, evclass=evclass, evclasskey=evclasskey)
            except Exception, e:
                logging.error("Zenoss Create Event: Failed to create event - %s" % e)
                sys.exit(1)

if __name__ == '__main__':
    main()
