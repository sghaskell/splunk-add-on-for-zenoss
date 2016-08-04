import sys
import os
from cfgparse import ConfigParser
import base64
import cPickle as pickle

APPS_DIR = "etc/apps/TA-zenoss"
BIN_DIR = "etc/apps/TA-zenoss/bin"
ZENOSS_SERVER_CONFIG = "local/zenoss_servers.conf"
HASH_CHK_FILE = ".server_config_hash"

class ZenossServerConfig:
    def __init__(self, stanza, force=False):
        self.splunk_home = os.environ['SPLUNK_HOME']
        self._hash_chk_file = "%s/%s/%s" % (self.splunk_home, BIN_DIR, HASH_CHK_FILE)
        self.config_path = "%s/%s/%s" % (self.splunk_home, APPS_DIR, ZENOSS_SERVER_CONFIG)
        self.stanza = stanza
        self.username = None
        self.password = None
        self.web_address = None
        self.config = self._read_config()

        if force:
            return

        if self._check_hash(self.stanza):
            self.password = base64.b64decode(self.password)
        else:
            try:
                f = self._open_chk_file("r")
                hash_dict = self._load_pickle(f)
                f.close()
                hash_dict['hashed'].append(self.stanza)
            except EOFError:
                hash_dict = { 'hashed' : [self.stanza] } 

            self._hash_password()
            self.config = self._read_config()
            self.password = base64.b64decode(self.password)
            self._write_hash_file(hash_dict)
           
    def _open_chk_file(self, mode):
        try:
            f = open(self._hash_chk_file, mode)
        except Exception:
            sys.stderr.write("Failed to open file %s -- Creating\n" % (self._hash_chk_file))
            open(self._hash_chk_file, 'w+').close()
            f = open(self._hash_chk_file, mode)
        return f

    def _load_pickle(self, f):
        return pickle.load(f)

    def _check_hash(self, stanza):
        f = self._open_chk_file("r+")
        try:
            hash_pickle = self._load_pickle(f)
            f.close()
            if stanza in hash_pickle['hashed']:
                return True
            else:
                return False 
        except EOFError:
            return False
                    
    def _write_hash_file(self, hash_dict):
        f = self._open_chk_file("w+")
        pickle.dump(hash_dict, f)
        f.close()
        
    def _read_config(self):
        if not os.path.exists(self.config_path):
            sys.stderr.write("Config file does not exist: %s\n" % self.config_path)
            sys.exit(1)

        c = ConfigParser()
        config = c.add_file(self.config_path)
        try:
            self.username = c.add_option('username', keys = self.stanza).get()
            self.password = c.add_option('password', keys = self.stanza).get()
            self.web_address = c.add_option('web_address', keys = self.stanza).get()
        except Exception, e:
            sys.stderr.write("Faled to parse config - %s\n" % e)
            sys.exit(1)

        return config

    def _hash_password(self, password=None):
        if(password):
            pw_hash = base64.b64encode(password)
        else:
            pw_hash = base64.b64encode(self.password)
        try:
            f = open(self.config_path, 'w+')
        except Exception, e:
            sys.stderr.write("%s" % e)
            sys.exit(1)

        self.config.set_option('password', pw_hash, keys = self.stanza)
        self.config.write(f)
        f.close()
