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
import requests
from requests.auth import HTTPProxyAuth
import re

from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

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
    def __init__(self, server, username, password, proxy_uri=None, proxy_username=None,
            proxy_password=None, no_ssl_cert_check=False, cafile=None, debug=False):
        self.ZENOSS_INSTANCE = server.rstrip("/")
        if not self.ZENOSS_INSTANCE.startswith("https://"):
            raise Exception("URL Scheme for Zenoss Instance must be 'https://'. Got {}".format(server))
        self.ZENOSS_USERNAME = username
        self.ZENOSS_PASSWORD = password
        self.isZenossCloud = re.match(r'^.*\/(cz)\d+.*', self.ZENOSS_INSTANCE)
        self.tid = 1
        self.auth = None

        self.session = requests.Session()
        self.session.verify = no_ssl_cert_check
        self.session.cert = cafile
        if proxy_uri:
            proxies = {'http': proxy_uri, 'https': proxy_uri}
            if proxy_username:
                # Support Proxy Basic Authentication
                self.auth = HTTPProxyAuth(proxy_username, proxy_password)
            self.session.proxies.update(proxies)

        # Skip simple auth if Zenoss Cloud URI detected
        if(not self.isZenossCloud):
            """
            Initialize the API connection, log in, and store authentication cookie
            """
            data = {
                "__ac_name": self.ZENOSS_USERNAME,
                "__ac_password": self.ZENOSS_PASSWORD,
                "submitted": True,
                "came_from": "{}/zport/dmd".format(self.ZENOSS_INSTANCE)
            }
            
            url = "{}/zport/acl_users/cookieAuthHelper/login".format(self.ZENOSS_INSTANCE)
            
            self.session.post(url, data=data, auth=self.auth)

    def _router_request(self, router, method, data=[]):
        if router not in ROUTERS:
            raise Exception("Router '{0}' not available.".format(router))

        # Contruct a standard URL request for API calls
        url = "{0}/zport/dmd/{1}_router".format(self.ZENOSS_INSTANCE, ROUTERS[router])

        # NOTE: Content-type MUST be set to 'application/json' for these requests
        header = {
            'Content-Type': 'application/json'
        }

        # Set z-api-key for Zenoss Cloud
        if(self.isZenossCloud):
            header['z-api-key'] = self.ZENOSS_PASSWORD

        # Convert the request parameters into JSON
        payload = json.dumps({
                    'action': router,
                    'method': method,
                    'data': data,
                    'type': 'rpc',
                    'tid': self.tid
                })

        # Increment the request count ('tid'). More important if sending multiple
        # calls in a single request
        self.tid += 1

        # Submit the request and convert the returned JSON to objects
        response = self.session.post(url, headers=header, data=payload, auth=self.auth)

        # The API returns a 200 response code even whe auth is bad.
        # With bad auth, the login page is displayed. Here I search for
        # an element on the login form to determine if auth failed.
        if re.search('name="__ac_name"', response.content.decode("utf-8")):
            raise Exception('Request failed. Bad username/password.')
        if response.status_code != 200:
            raise Exception("Unable to complete request. HTTP Error [{}]: {}".format(
                response.status_code,
                response.text,
            ))

        return response.json()

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
                   limit=1000):
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
