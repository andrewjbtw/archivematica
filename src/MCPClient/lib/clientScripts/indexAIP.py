#!/usr/bin/python2 -OO

import ConfigParser
from glob import glob
import os
import sys

path = "/usr/lib/archivematica/archivematicaCommon"
if path not in sys.path:
    sys.path.append(path)
import databaseInterface
import elasticSearchFunctions
from executeOrRunSubProcess import executeOrRun
import storageService as storage_service
from identifer_functions import extract_identifiers_from_mods


def list_mods(sip_path):
    return glob('{}/submissionDocumentation/**/mods/*.xml'.format(sip_path))


def index_aip():
    """ Write AIP information to ElasticSearch. """
    sip_uuid = sys.argv[1]  # %SIPUUID%
    sip_name = sys.argv[2]  # %SIPName%
    sip_path = sys.argv[3]  # %SIPDirectory%
    sip_type = sys.argv[4]  # %SIPType%

    # Check if ElasticSearch is enabled
    client_config_path = '/etc/archivematica/MCPClient/clientConfig.conf'
    config = ConfigParser.SafeConfigParser()
    config.read(client_config_path)
    elastic_search_disabled = False
    try:
        elastic_search_disabled = config.getboolean(
            'MCPClient', "disableElasticsearchIndexing")
    except ConfigParser.NoOptionError:
        pass
    if elastic_search_disabled:
        print 'Skipping indexing: indexing is currently disabled in {}.'.format(client_config_path)
        return 0

    print 'sip_uuid', sip_uuid
    aip_info = storage_service.get_file_info(uuid=sip_uuid)
    print 'aip_info', aip_info
    aip_info = aip_info[0]

    mets_name = 'METS.{}.xml'.format(sip_uuid)
    mets_path = os.path.join(sip_path, mets_name)

    mods_paths = list_mods(sip_path)
    identifiers = []
    for mods in mods_paths:
        identifiers.extend(extract_identifiers_from_mods(mods))

    # If this is an AIC, find the number of AIP stored in it and index that
    aips_in_aic = None
    if sip_type == "AIC":
        sql = """SELECT variableValue FROM UnitVariables WHERE unitType='SIP' AND unitUUID='%s' AND variable='AIPsinAIC';""" % (sip_uuid,)
        rows = databaseInterface.queryAllSQL(sql)
        if rows:
            aips_in_aic = rows[0][0]

    elasticSearchFunctions.connect_and_index_aip(
        sip_uuid,
        sip_name,
        aip_info['current_full_path'],
        mets_path,
        size=aip_info['size'],
        aips_in_aic=aips_in_aic,
        identifiers=identifiers)

    return 0


if __name__ == '__main__':
    sys.exit(index_aip())
