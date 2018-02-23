# New in 2.0
The 2.0 release brings the Zenoss Event custom alert action and the credential management dashboard.

# Requirements
You must be in the **admin role** or have the **admin_all_objects** capability enabled to use the Credential Management dashboard and schedule the Zenoss Event custom alert action.

# Zenoss Compatibility
This has been tested against and is known to be compatible with Zenoss 4.x and 5.x.

# Configure Modular Input
**Settings -> Data inputs -> Zenoss**

**Username**: zenoss username  
**password**: zenoss password  
**Zenoss Web Interface**: Web interface to Zenoss server; e.g.http://zenoss-server:8080 or https://zenoss5.myhost.mydomain for Zenoss 5.x connections.
**Device Name (Optional)**: Filter to only pull from a specific device. Defaults to all devices
**Disable SSL Certificate Verification**: Zenoss 5.x installs - check to disable SSL verification. **WARNING** This is a potentially dangerous option.
**CA File**: Optional: Zenoss 5.x installs - specify certificate authority file in PEM format for certificates signed by untrusted root authority
**Timezone (Optional)**: Timezone of Zenoss server - see [http://en.wikipedia.org/wiki/List_of_tz_database_time_zones](http://en.wikipedia.org/wiki/List_of_tz_database_time_zones)  
**Archive Threshold**: Zenoss 'Event Archive Threshold (minutes)' setting. Interval to read archive table. Leave blank for Zenoss default of 4320.  
**Event Checkpoint Removal**: Zenoss 'Delete Archived Events Older Than (days)' setting. Used to keep checkpoint file clean. Leave blank for Zenoss default of 90.  
**Start Date (Optional)**: Specify a starting date to pull events from or leave blank for ALL events. Ex: 2015-03-16T00:00:00  
**Index Closed Events (Optional)**: Index eventState "Closed"  
**Index Cleared Events (Optional)**: Index eventState "Cleared"  
**Index Archived Events (Optional)**: Index events form the Archive table  
**Index Suppressed Events (Optional)**: Index eventState "Suppressed"             
**Index Repeat Events (Optional)**: Index repeat events. Index an event every time the count increments for an evid. This will result in the same event getting indexed with a new latestTime timestamp. This is useful for fine grained analytics on events. This setting could lead to an increase in indexing volume depending on your environment.            
**Sourcetype**: Set to Manual and leave blank to set to 'zenoss-events'  
            
##More Settings
**Interval**: Defaults to 60 seconds  
**Host**: specify zenoss hostname  
**Index**: specify zenoss index  

# Credential Management
Use the **Credential Management** dashboard to securely store credentials for your Zenoss server instances. The dashboard is a CRUD interface to the storage/passwords REST endpoint. You can **create, update, delete and reveal the password** for any credentials stored. Right click on any row to reveal a context menu for the **update** and **delete** actions. You can also leverage the realm field to describe a connection; e.g. - prod or dev.

# Configuring Zenoss Event Custom Alert Action

**1)** Create credentials for your Zenoss instance using the Credential Management dashboard. Credentials will be securely stored in the storage/passwords REST endpoint and accessed by the Zenoss Event custom alert action. Please re-read the **Requirements** section before moving on.
        
**2)** Create a saved search that meets your criteria for creating an event. The alert script requires field/table output with the following names (case sensitive):

**device OR host (REQUIRED)** - device/host name  
**severity (REQUIRED)** - severity of alert - "Critical" OR "Error" OR "Warning" OR "Info" OR "Debug" OR "Clear"  
**summary (REQUIRED)** - Plain text summary of the event  
**component (OPTIONAL)** - Component name  
**evclass (OPTIONAL)** - Event class name  
**evclasskey (OPTIONAL)** - Event class key  
        
### example search

    index=oidemo sourcetype=access_combined | stats count(eval(status="404")) as web_error by host | eval severity=case(web_error > 100 AND web_error < 500, "Warning", web_error > 500 AND web_error < 1000, "Error", web_error > 1000, "Critical") | eval summary="Web 404 Error - greater than 1000 errors" | eval evclass="/Status/Web" | table host, severity, summary, evclass
          
**3)** Save the search as an Alert and schedule it to run per your desired frequency. Set to trigger for each result. Under **Add Actions** select **Zenoss Event**. Fill in the required fields. Reference the credential account and optionally the realm to authenticate with your Zenoss instance. An event for each row in the table will be generated in Zenoss when the alert is triggered.

# Debugging
View the customer alert aciton log located at `$SPLUNK_HOME/var/log/splunk/zenoss_event_modalert.log` to troubleshoot issues with the Zenoss Event custom alert action.

# Data Model
The app ships with a Data Model that comes unaccelerated out of the box. To acclerate the data model go to **'Settings -> Data models'**. Under **'Actions'** for the **_Events_** data model, select **'Edit -> Edit Acceleration'** and select the summary range that fits your needs.
        
# CIM Compliant
This app is CIM compliant and maps to the Alerts data model.
[http://docs.splunk.com/Documentation/CIM/latest/User/Alerts](http://docs.splunk.com/Documentation/CIM/latest/User/Alerts)
