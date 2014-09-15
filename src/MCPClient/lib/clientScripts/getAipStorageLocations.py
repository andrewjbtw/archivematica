#!/usr/bin/python2 -OO

import logging
import os
import sys

path = "/usr/lib/archivematica/archivematicaCommon"
if path not in sys.path:
    sys.path.append(path)
from custom_handlers import GroupWriteRotatingFileHandler
import storageService as storage_service

logger = logging.getLogger('archivematica.mcp.client')
logger.addHandler(GroupWriteRotatingFileHandler("/var/log/archivematica/archivematica.log",
    maxBytes=4194304))
logger.setLevel(logging.INFO)

# Set up Django settings
path = '/usr/share/archivematica/dashboard'
if path not in sys.path:
    sys.path.append(path)
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings.common'


def get_aip_storage_locations(purpose):
    """ Return a dict of AIP Storage Locations and their descriptions."""
    storage_directories = storage_service.get_location(purpose=purpose)
    logging.debug("Storage Directories: {}".format(storage_directories))
    choices = {}
    for storage_dir in storage_directories:
        choices[storage_dir['description']] = storage_dir['resource_uri']
    print choices


if __name__ == '__main__':
    try:
        purpose = sys.argv[1]
    except IndexError:
        purpose = "AS"
    get_aip_storage_locations(purpose)
