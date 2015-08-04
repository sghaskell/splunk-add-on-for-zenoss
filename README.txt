Requirments
===========
This TA requires Python. It can be installed on a search head, heavy forwarder
or light forwarder. The TA will not work on a universal forwarder due to the
Python dependency. If installed on a search head in a distributed environment
make sure you are forwarding data from your search head to your indexers.

http://docs.splunk.com/Documentation/Splunk/6.2.3/DistSearch/Forwardsearchheaddata

Install Instructions
====================
Extract in $SPLUNK_HOME/etc/apps or install via the UI.

Configure Modular Input
=======================
Settings -> Data inputs -> Zenoss

Username: zenoss username
password: zenoss password
Zenoss Web Interface: Web interface to Zenoss server; e.g.
http://zenoss-server:8080
Device Name (Optional): Filter to only pull from a specific device. Defaults
to all devices
Timezone (Optional): Timezone of Zenoss server - see
http://en.wikipedia.org/wiki/List_of_tz_database_time_zones
Archive Threshold - Zenoss 'Event Archive Threshold (minutes)' setting.
Interval to read archive table. Leave blank for Zenoss default of 4320.
Event Checkpoint Removal - Zenoss 'Delete Archived Events Older Than (days)'
setting. Used to keep checkpoint file clean. Leave blank for Zenoss default of
90.
Start Date (Optional): Specify a starting date to pull events from or leave
blank for ALL events. Ex: 2015-03-16T00:00:00
Index Closed Events (Optional): Index eventState "Closed"
Index Cleared Events (Optional): Index eventState "Cleared"
Index Archived Events (Optional): Index events form the Archive table
Index Suppressed Events (Optional): Index eventState "Suppressed"            
Index Repeat Events (Optional): Index repeat events. Index an event every time
the count increments for an evid. This will result in the same event getting
indexed with a new latestTime timestamp. This is useful for fine grained
analytics on events. This setting could lead to an increase in indexing volume
depending on your environment.            
Sourcetype - Set to Manual and leave blank to set to 'zenoss-events'
            
More Settings
Interval - Defaults to 60 seconds
Host - specify zenoss hostname
Index - specify zenoss index
          
Configuring Event Creation Alert Script
========================================
1) Edit $SPLUNK_HOME/etc/apps/TA-zenoss/local/zenoss_servers.conf

Copy the example stanza and update with your Zenoss server specifics

# Example
[zenoss]
username = admin
password = mysecurepassword 
web_address = http://zenoss:8080
        
The password will get hashed the first time an alert is triggered.

2) Edit $SPLUNK_HOME/etc/apps/TA-zenoss/bin/scripts/zenoss_create_event.sh and
update the script with the stanza from the previous step. In this example
'zenoss'.

ZENOSS_SERVER_STANZA=zenoss
        
3) Create a saved search that meets your criteria for creating an event. The
alert script requires field/table output with the following names (case
sensitive):

device OR host (REQUIRED) - device/host name
severity (REQUIRED) - severity of alert - "Critical" OR "Error" OR "Warning"
OR "Info" OR "Debug" OR "Clear"
summary (REQUIRED) - Plain text summary of the event
component (OPTIONAL) - Component name
evclass (OPTIONAL) - Event class name
evclasskey (OPTIONAL) - Event class key
        
example search

index=oidemo sourcetype=access_combined | stats count(eval(status="404")) as
web_error by host | eval severity=case(web_error > 100 AND web_error < 500,
"Warning", web_error > 500 AND web_error < 1000, "Error", web_error > 1000,
"Critical") | eval summary="Web 404 Error - greater than 1000 errors" | eval
evclass="/Status/Web" | table host, severity, summary, evclass
          
4) Save the search as an Alert and schedule it to run per your desired
frequency. Under 'Enable Actions' check 'Run a Script'. In the 'Filename'
field enter 'zenoss_create_event.sh'. An event for each row in the table will
be generated in Zenoss when the alert is triggered.

Updating Zenoss Server Password
===============================
A script is provided to update the password in
$SPLUNK_HOME/etc/apps/TA-zenoss/local/zenoss_servers.conf for a given stanza.
The following examples demonstrates updating the password for the zenoss
stanza in the example config above.

$SPLUNK_HOME/bin/splunk cmd python
$SPLUNK_HOME/etc/apps/TA-zenoss/bin/update_password.py -s zenoss -f
$SPLUNK_HOME/etc/apps/TA-zenoss/local/zenoss_servers.conf -p
mynewsecurepassword
        
CIM Compliant
=============
This app is CIM compliant and maps to the Alerts data model.
http://docs.splunk.com/Documentation/CIM/latest/User/Alerts
