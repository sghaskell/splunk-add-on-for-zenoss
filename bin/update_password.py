import sys
import os
import argparse
import gzip
import csv
import logging
from pprint import pprint
from zenoss_server_config import ZenossServerConfig

def parse_args():
    argparser = argparse.ArgumentParser(description='Update Zenoss password')
    argparser.add_argument('-s', '--stanza', required=True,
                            help='stanza')
    argparser.add_argument('-f', '--file', required=True,
                            help='results file')
    argparser.add_argument('-p', '--password', required=True,
                            help='password')
    flags = argparser.parse_args()

    return flags

def main():
    flags = parse_args()
    config = ZenossServerConfig(flags.stanza, force=True)
    config._hash_password(password=flags.password)

if __name__ == '__main__':
    main()
