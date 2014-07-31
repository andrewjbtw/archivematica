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

MD_TYPE_SIP = models.MetadataAppliesToType.objects.get(description='SIP')


def parse_files(mets_path):
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
        try:
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
        except fpr_models.FormatVersion.DoesNotExist:
            pass
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


def parse_dc(sip_uuid, root):
    # Delete existing DC
    models.DublinCore.objects.filter(metadataappliestoidentifier=sip_uuid, metadataappliestotype=MD_TYPE_SIP).delete()
    # Parse DC
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
        # Only want SIP DC, not file DC
        div = root.find('mets:structMap/mets:div/mets:div[@TYPE="Directory"][@LABEL="objects"]', namespaces=ns.NSMAP)
        dmdids = div.get('DMDID')
        # No SIP DC
        if dmdids is None:
            return
        dmdids = dmdids.split()
        for dmd in dmds[::-1]:  # Reversed
            if dmd.get('ID') in dmdids:
                dc_xml = dmd.find('mets:mdWrap/mets:xmlData/dcterms:dublincore', namespaces=ns.NSMAP)
                break
        dc_model = models.DublinCore(
            metadataappliestoidentifier=sip_uuid,
            metadataappliestotype=MD_TYPE_SIP,
            status=models.METADATA_STATUS_REINGEST,
        )
        print('Dublin Core:')
        for elem in dc_xml:
            tag = elem.tag.replace(ns.dctermsBNS, '', 1)
            print(tag, elem.text)
            setattr(dc_model, DC_TERMS_MATCHING[tag], elem.text)
        dc_model.save()

def parse_rights(sip_uuid, root):
    # Delete existing PREMIS Rights
    del_rights = models.RightsStatement.objects.filter(metadataappliestoidentifier=sip_uuid, metadataappliestotype=MD_TYPE_SIP)
    # TODO delete all the other rights things?
    models.RightsStatementCopyright.objects.filter(rightsstatement__in=del_rights).delete()

    models.RightsStatementRightsGranted.objects.filter(rightsstatement__in=del_rights).delete()
    del_rights.delete()

    amds = root.xpath('mets:amdSec/mets:rightsMD/parent::*', namespaces=ns.NSMAP)
    if amds:
        amd = amds[0]
        # Get rightsMDs
        # METS from original AIPs will not have @STATUS, and reingested AIPs will have only one @STATUS that is 'updated'
        rights_stmts = amd.xpath('mets:rightsMD[not(@STATUS) or @STATUS="current"]/mets:mdWrap[@MDTYPE="PREMIS:RIGHTS"]/*/premis:rightsStatement', namespaces=ns.NSMAP)

        # Parse to DB
        for statement in rights_stmts:
            rights_basis = statement.findtext('premis:rightsBasis', namespaces=ns.NSMAP)
            print('rights_basis', rights_basis)
            rights = models.RightsStatement.objects.create(
                metadataappliestotype=MD_TYPE_SIP,
                metadataappliestoidentifier=sip_uuid,
                rightsstatementidentifiertype="",
                rightsstatementidentifiervalue="",
                rightsbasis=rights_basis,
                status=models.METADATA_STATUS_REINGEST,
            )
            # TODO parse more than just Copyright
            if rights_basis == 'Copyright':
                cr_status = statement.findtext('.//premis:copyrightStatus', namespaces=ns.NSMAP) or ""
                cr_jurisdiction = statement.findtext('.//premis:copyrightJurisdiction', namespaces=ns.NSMAP) or ""
                cr_det_date = statement.findtext('.//premis:copyrightStatusDeterminationDate', namespaces=ns.NSMAP) or ""
                cr_start_date = statement.findtext('.//premis:copyrightApplicableDates/premis:startDate', namespaces=ns.NSMAP) or ""
                cr_end_date = statement.findtext('.//premis:copyrightApplicableDates/premis:endDate', namespaces=ns.NSMAP) or ""
                cr_end_open = False
                if cr_end_date == 'OPEN':
                    cr_end_open = True
                    cr_end_date = None
                cr = models.RightsStatementCopyright.objects.create(
                    rightsstatement=rights,
                    copyrightstatus=cr_status,
                    copyrightjurisdiction=cr_jurisdiction,
                    copyrightstatusdeterminationdate=cr_det_date,
                    copyrightapplicablestartdate=cr_start_date,
                    copyrightapplicableenddate=cr_end_date,
                    copyrightenddateopen=cr_end_open,
                )
                cr_id_type = statement.findtext('.//premis:copyrightDocumentationIdentifierType', namespaces=ns.NSMAP) or ""
                cr_id_value = statement.findtext('.//premis:copyrightDocumentationIdentifierValue', namespaces=ns.NSMAP) or ""
                cr_id_role = statement.findtext('.//premis:copyrightDocumentationRole', namespaces=ns.NSMAP) or ""
                models.RightsStatementCopyrightDocumentationIdentifier.objects.create(
                    rightscopyright=cr,
                    copyrightdocumentationidentifiertype=cr_id_type,
                    copyrightdocumentationidentifiervalue=cr_id_value,
                    copyrightdocumentationidentifierrole=cr_id_role,
                )
                cr_note = statement.findtext('.//premis:copyrightNote', namespaces=ns.NSMAP) or ""
                models.RightsStatementCopyrightNote.objects.create(
                    rightscopyright=cr,
                    copyrightnote=cr_note,
                )

            # Parse rightsGranted
            rights_act = statement.findtext('.//premis:rightsGranted/premis:act', namespaces=ns.NSMAP) or ""
            rights_start_date = statement.findtext('.//premis:rightsGranted/premis:termOfRestriction/premis:startDate', namespaces=ns.NSMAP) or ""
            rights_end_date = statement.findtext('.//premis:rightsGranted/premis:termOfRestriction/premis:endDate', namespaces=ns.NSMAP) or ""
            rights_end_open = False
            if rights_end_date == 'OPEN':
                rights_end_date = None
                rights_end_open = True
            print('rights_act', rights_act)
            print('rights_start_date', rights_start_date)
            print('rights_end_date', rights_end_date)
            print('rights_end_open', rights_end_open)
            rights_granted = models.RightsStatementRightsGranted.objects.create(
                rightsstatement=rights,
                act=rights_act,
                startdate=rights_start_date,
                enddate=rights_end_date,
                enddateopen=rights_end_open,
            )

            rights_note = statement.findtext('.//premis:rightsGranted/premis:rightsGrantedNote', namespaces=ns.NSMAP) or ""
            print('rights_note', rights_note)
            models.RightsStatementRightsGrantedNote.objects.create(
                rightsgranted=rights_granted,
                rightsgrantednote=rights_note,
            )

            rights_restriction = statement.findtext('.//premis:rightsGranted/premis:restriction', namespaces=ns.NSMAP) or ""
            print('rights_restriction', rights_restriction)
            models.RightsStatementRightsGrantedRestriction.objects.create(
                rightsgranted=rights_granted,
                restriction=rights_restriction,
            )


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
    # HACK Most of this file is a hack to parse the METS file into the DB.
    # This should use the in-progress METS Reader/Writer

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
    files = parse_files(mets_path)

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
        if file_info['format_version']:
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

    root = etree.parse(mets_path)

    parse_dc(sip_uuid, root)

    parse_rights(sip_uuid, root)

    # Update processingMCP
    processing_path = os.path.join(sip_path, 'processingMCP.xml')
    update_default_config(processing_path)


if __name__ == '__main__':
    print('METS Reader')
    sys.exit(main())
