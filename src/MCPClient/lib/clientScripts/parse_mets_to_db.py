#!/usr/bin/python2

from __future__ import print_function
import datetime
from lxml import etree
import sys
import os

import archivematicaXMLNamesSpace as ns

sys.path.append("/usr/lib/archivematica/archivematicaCommon")
import fileOperations
import databaseFunctions
import databaseInterface

sys.path.append('/usr/share/archivematica/dashboard')
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings.common'
from main import models
from fpr import models as fpr_models


def parse_mets(mets_path):
    # HACK this is a hack to populate files with information from the METS file.
    # This should use the in-progress METS Reader/Writer
    root = etree.parse(mets_path)
    filesec = root.find('.//mets:fileSec', namespaces=ns.NSMAP)
    files = []

    for fe in filesec.findall('.//mets:file', namespaces=ns.NSMAP):
        filegrpuse = fe.getparent().get('USE')
        print('filegrpuse', filegrpuse)

        amdid = fe.get('ADMID')
        print('amdid', amdid)
        amdsec = root.find('.//mets:amdSec[@ID="'+amdid+'"]', namespaces=ns.NSMAP)

        file_uuid = amdsec.findtext('.//premis:objectIdentifierValue', namespaces=ns.NSMAP)
        print('file_uuid', file_uuid)

        original_path = amdsec.findtext('.//premis:originalName', namespaces=ns.NSMAP)
        original_path = original_path.replace('%transferDirectory%', '%SIPDirectory%')
        print('original_path', original_path)

        current_path = fe.find('mets:FLocat', namespaces=ns.NSMAP).get(ns.xlinkBNS+'href')
        current_path = '%SIPDirectory%' + current_path
        print('current_path', current_path)

        checksum = amdsec.findtext('.//premis:messageDigest', namespaces=ns.NSMAP)
        print('checksum', checksum)

        size = amdsec.findtext('.//premis:size', namespaces=ns.NSMAP)
        print('size', size)

        # FormatVersion
        format_version = None
        # Looks for PRONOM ID first
        if amdsec.findtext('.//premis:formatRegistryName', namespaces=ns.NSMAP) == 'PRONOM':
            puid = amdsec.findtext('.//premis:formatRegistryKey', namespaces=ns.NSMAP)
            print('PUID', puid)
            format_version = fpr_models.FormatVersion.active.get(pronom_id=puid)
        elif amdsec.findtext('.//premis:formatRegistryName', namespaces=ns.NSMAP) == 'Archivematica Format Policy Registry':
            key = amdsec.findtext('.//premis:formatRegistryKey', namespaces=ns.NSMAP)
            print('FPR key', key)
            format_version = fpr_models.IDRule.active.get(command_output=key).format
        # If not, look for formatName
        if not format_version:
            name = amdsec.findtext('.//premis:formatName', namespaces=ns.NSMAP)
            print('Format name', name)
            format_version = fpr_models.FormatVersion.active.get(description=name)
        print('format_version', format_version)

        # Derivation
        derivation = derivation_event = None
        event = amdsec.findtext('.//premis:relatedEventIdentifierValue', namespaces=ns.NSMAP)
        print('derivation event', event)
        related_uuid = amdsec.findtext('.//premis:relatedObjectIdentifierValue', namespaces=ns.NSMAP)
        print('related_uuid', related_uuid)
        rel = amdsec.findtext('.//premis:relationshipSubType', namespaces=ns.NSMAP)
        print('relationship', rel)
        if rel == 'is source of':
            derivation = related_uuid
            derivation_event = event

        file_info = {
            'uuid': file_uuid,
            'original_path': original_path,
            'current_path': current_path,
            'use': filegrpuse,
            'checksum': checksum,
            'size': size,
            'format_version': format_version,
            'derivation': derivation,
            'derivation_event': derivation_event,
        }

        files.append(file_info)
        print()

    return files


def update_default_config(processing_path):
    root = etree.parse(processing_path)

    # Do not run file ID in ingest
    ingest_id_mscl = '7a024896-c4f7-4808-a240-44c87c762bc5'
    use_existing_choice = models.MicroServiceChoiceReplacementDic.objects.filter(choiceavailableatlink=ingest_id_mscl).get(description='Use existing data')
    try:
        applies_to = root.xpath('//appliesTo[text()="%s"]' % ingest_id_mscl)[0]
    except IndexError:
        # Entry did not existing in preconfigured choices, so create
        choices = root.find('preconfiguredChoices')
        choice = etree.SubElement(choices, 'preconfiguredChoice')
        applies_to = etree.SubElement(choice, 'appliesTo').text = ingest_id_mscl
        go_to_chain = etree.SubElement(choice, 'goToChain')
    else:
        # Update existing entry
        go_to_chain = applies_to.getnext()
    go_to_chain.text = use_existing_choice.id

    # If normalize option has 'preservation', remove
    normalize_mscl = 'cb8e5706-e73f-472f-ad9b-d1236af8095f'
    try:
        applies_to = root.xpath('//appliesTo[text()="%s"]' % normalize_mscl)[0]
    except IndexError:
        # Entry did not existing in preconfigured choices
        pass
    else:
        # Update existing entry
        go_to_chain = applies_to.getnext()
        chain = models.MicroServiceChain.objects.get(pk=go_to_chain.text)
        if 'preservation' in chain.description:
            # Remove from processing MCP
            choice = go_to_chain.getparent()
            choice.getparent().remove(choice)

    # Write out processingMCP
    with open(processing_path, 'w') as f:
        f.write(etree.tostring(root, pretty_print=True))


def main():
    sip_uuid = sys.argv[1]
    task_uuid = sys.argv[2]
    sip_path = sys.argv[3]
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Set reingest type
    # TODO also support AIC-REIN
    sip = models.SIP.objects.filter(uuid=sip_uuid)
    sip.update(sip_type='AIP-REIN')

    # Stuff to delete
    # The cascading delete of the SIP on approve reingest deleted most things

    # Parse METS to extract information needed by later microservices
    mets_path = os.path.join(sip_path, 'metadata', 'submissionDocumentation', 'METS.'+sip_uuid+'.xml')
    files = parse_mets(mets_path)

    # Add information to the DB
    for file_info in files:
        # Add file & reingest event
        fileOperations.addFileToSIP(
            filePathRelativeToSIP=file_info['original_path'],
            fileUUID=file_info['uuid'],
            sipUUID=sip_uuid,
            taskUUID=task_uuid,
            date=now,
            sourceType="reingestion",
            use=file_info['use'],
        )
        # Update other file info
        # Cannot use Django ORM to fetch & update file, as it interacts poorly
        # with using raw SQL updates.  If ORM has been used at all before raw
        # SQL is run, the ORM cannot find the new file.
        sql = """UPDATE Files SET checksum='%s',fileSize='%s',currentLocation='%s' WHERE fileUUID='%s';""" % (file_info['checksum'], file_info['size'], file_info['current_path'], file_info['uuid'])
        databaseInterface.runSQL(sql)
        # Add Format ID
        models.FileFormatVersion.objects.create(
            file_uuid_id=file_info['uuid'],
            format_version=file_info['format_version']
        )

    # Derivation info
    # Has to be separate loop, as derived file may not be in DB otherwise
    # May not need to be parsed, if Derivation info can be roundtripped in METS Reader/Writer
    for file_info in files:
        if file_info['derivation'] is None:
            continue
        databaseFunctions.insertIntoDerivations(
            sourceFileUUID=file_info['uuid'],
            derivedFileUUID=file_info['derivation'],
            relatedEventUUID=file_info['derivation_event'],
        )

    # Delete existing DC
    md_type_sip = models.MetadataAppliesToType.objects.get(description='SIP')
    models.DublinCore.objects.filter(metadataappliestoidentifier=sip_uuid, metadataappliestotype=md_type_sip).delete()
    # Parse DC
    root = etree.parse(mets_path)
    dmds = root.xpath('mets:dmdSec/mets:mdWrap[@MDTYPE="DC"]/parent::*', namespaces=ns.NSMAP)
    # Find which DC to parse into DB
    if len(dmds) > 0:
        DC_TERMS_MATCHING = {
            'title': 'title',
            'creator': 'creator',
            'subject': 'subject',
            'description': 'description',
            'publisher': 'publisher',
            'contributor': 'contributor',
            'date': 'date',
            'type': 'type',
            'format': 'format',
            'identifier': 'identifier',
            'source': 'source',
            'relation': 'relation',
            'language': 'language',
            'coverage': 'coverage',
            'rights': 'rights',
            'isPartOf': 'is_part_of',
        }
        # Want most recently updated
        dmds = sorted(dmds, key=lambda e: e.get('CREATED'))
        dc_xml = dmds[-1].find('mets:mdWrap/mets:xmlData/dcterms:dublincore', namespaces=ns.NSMAP)
        dc_model = models.DublinCore(
            metadataappliestoidentifier=sip_uuid,
            metadataappliestotype=md_type_sip,
            status=models.METADATA_STATUS_REINGEST,
        )
        print('Dublin Core:')
        for elem in dc_xml:
            tag = elem.tag.replace(ns.dctermsBNS, '', 1)
            print(tag, elem.text)
            setattr(dc_model, DC_TERMS_MATCHING[tag], elem.text)
        print('status', dc_model.status)
        dc_model.save()
        print('status', dc_model.status)

    # Delete existing PREMIS Rights
    models.RightsStatement.objects.filter(metadataappliestoidentifier=sip_uuid, metadataappliestotype=md_type_sip).delete()
    # TODO delete all the other rights things?

    amds = root.xpath('mets:amdSec/mets:rightsMD/parent::*', namespaces=ns.NSMAP)
    if amds:
        amd = amds[0]
        # Get rightsMDs
        # METS from original AIPs will not have @STATUS, and reingested AIPs will have only one @STATUS that is 'updated'
        rights_stmts = amd.xpath('mets:rightsMD[not(@STATUS) or @STATUS="updated"]/mets:mdWrap[@MDTYPE="PREMIS:RIGHTS"]/*/premis:rightsStatement', namespaces=ns.NSMAP)

        # Parse to DB
        for statement in rights_stmts:
            id_type = statement.findtext('premis:rightsStatementIdentifier/premis:rightsStatementIdentifierType', namespaces=ns.NSMAP)
            id_value = statement.findtext('premis:rightsStatementIdentifier/premis:rightsStatementIdentifierValue', namespaces=ns.NSMAP)
            rights_basis = statement.findtext('premis:rightsBasis', namespaces=ns.NSMAP)
            print('rights_basis', rights_basis)
            rights = models.RightsStatement(
                metadataappliestotype=md_type_sip,
                metadataappliestoidentifier=sip_uuid,
                rightsstatementidentifiertype=id_type,
                rightsstatementidentifiervalue=id_value,
                rightsbasis=rights_basis,
                status=models.METADATA_STATUS_REINGEST,
            )
            rights.save()
            # TODO parse more than just RightsStatement

    # Update processingMCP
    processing_path = os.path.join(sip_path, 'processingMCP.xml')
    update_default_config(processing_path)


if __name__ == '__main__':
    print('METS Reader')
    sys.exit(main())
