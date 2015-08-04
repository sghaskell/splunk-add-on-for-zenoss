#!/usr/bin/env python
# Zenoss-4.x JSON API Example (python)
#
# To quickly explore, execute 'python -i api_example.py'
#
# >>> z = ZenossAPI()
# >>> events = z.get_events()
# etc.

import json
import urllib
import urllib2


ROUTERS = { 'MessagingRouter': 'messaging',
        'EventsRouter': 'evconsole',
        'ProcessRouter': 'process',
        'ServiceRouter': 'service',
        'DeviceRouter': 'device',
        'NetworkRouter': 'network',
        'TemplateRouter': 'template',
        'DetailNavRouter': 'detailnav',
        'ReportRouter': 'report',
        'MibRouter': 'mib',
        'ZenPackRouter': 'zenpack' }

class ZenossAPI():
    def __init__(self, server, username, password, debug=False):
        self.ZENOSS_INSTANCE = server
        self.ZENOSS_USERNAME = username
        self.ZENOSS_PASSWORD = password

        """
        Initialize the API connection, log in, and store authentication cookie
        """
        # Use the HTTPCookieProcessor as urllib2 does not save cookies by default
        self.urlOpener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        if debug: self.urlOpener.add_handler(urllib2.HTTPHandler(debuglevel=1))
        self.reqCount = 1

        # Contruct POST params and submit login.
        loginParams = urllib.urlencode(dict(
                __ac_name = self.ZENOSS_USERNAME,
                __ac_password = self.ZENOSS_PASSWORD,
                submitted = 'true',
                came_from = self.ZENOSS_INSTANCE + '/zport/dmd'))
        self.urlOpener.open(self.ZENOSS_INSTANCE + '/zport/acl_users/cookieAuthHelper/login',
                    loginParams)

    def _router_request(self, router, method, data=[]):
        if router not in ROUTERS:
            raise Exception('Router "' + router + '" not available.')

        # Contruct a standard URL request for API calls
        req = urllib2.Request(self.ZENOSS_INSTANCE + '/zport/dmd/' +
                      ROUTERS[router] + '_router')

        # NOTE: Content-type MUST be set to 'application/json' for these requests
        req.add_header('Content-type', 'application/json; charset=utf-8')

        # Convert the request parameters into JSON
        reqData = json.dumps([dict(
                action=router,
                method=method,
                data=data,
                type='rpc',
                tid=self.reqCount)])

        # Increment the request count ('tid'). More important if sending multiple
        # calls in a single request
        self.reqCount += 1

        # Submit the request and convert the returned JSON to objects
        return json.loads(self.urlOpener.open(req, reqData).read())

    def get_devices(self, deviceClass='/zport/dmd/Devices'):
        return self._router_request('DeviceRouter', 'getDevices',
                        data=[{'uid': deviceClass,
                           'params': {} }])['result']

    def get_events(self, 
                   device=None,
                   component=None,
                   eventClass=None,
                   start=None,
                   archive=False,
                   last_time=None,
                   closed=None,
                   cleared=None,
                   suppressed=None,
                   limit=1000000000):
        data = dict(start=start, limit=limit, dir='DESC', sort='severity', archive=archive)
        if(archive):
            data['params'] = dict(severity=[5,4,3,2,0], eventState=[0,1,2,3,4,6])
        else:
            data['params'] = dict(severity=[5,4,3,2], eventState=[0,1])
            if(suppressed): data['params']['eventState'].append(2)
            if(closed): data['params']['eventState'].append(3)
            if(cleared): data['params']['eventState'].append(4)

        if(last_time): data['params']['lastTime'] = last_time
        
        if device: data['params']['device'] = device
        if component: data['params']['component'] = component
        if eventClass: data['params']['eventClass'] = eventClass

        return self._router_request('EventsRouter', 'query', [data])['result']


    def add_device(self, deviceName, deviceClass):
        data = dict(deviceName=deviceName, deviceClass=deviceClass)
        return self._router_request('DeviceRouter', 'addDevice', [data])

    def create_event_on_device(self, device, severity, summary, component=None, evclass=None, evclasskey=None):
        if severity not in ('Critical', 'Error', 'Warning', 'Info', 'Debug', 'Clear'):
            raise Exception('Severity "' + severity +'" is not valid.')

        data = dict(device=device, summary=summary, severity=severity,
                component=component, evclasskey=evclasskey, evclass=evclass)
        return self._router_request('EventsRouter', 'add_event', [data])
