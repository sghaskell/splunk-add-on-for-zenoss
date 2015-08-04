# Author: Scott Haskell
# Company: Splunk Inc.
# Date: 2015-05-13
# Description: 
#  Wrapper script to call Python script that generates Zenoss Alerts.
#  
# Arguments:
#  $8 - Path to raw results of search
#  See http://docs.splunk.com/Documentation/Splunk/latest/Alert/Configuringscriptedalerts
#  for all possible arguments

# Specify the name of the stanza in local/zenoss_servers.conf
# for the server you want to create events on
ZENOSS_SERVER_STANZA=zenoss

$SPLUNK_HOME/bin/splunk cmd python $SPLUNK_HOME/etc/apps/TA-zenoss/bin/zenoss_create_event.py -s $ZENOSS_SERVER_STANZA -f $SPLUNK_ARG_8
