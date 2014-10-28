#!/usr/bin/python -OO
# This file is part of Archivematica.
#
# Copyright 2010-2013 Artefactual Systems Inc. <http://artefactual.com>
#
# Archivematica is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Archivematica is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Archivematica.  If not, see <http://www.gnu.org/licenses/>.

# @package Archivematica
# @subpackage archivematicaCommon
# @author Joseph Perry <joseph@artefactual.com>

import csv
import os
import uuid
import sys
import shutil
from databaseFunctions import insertIntoFiles
from executeOrRunSubProcess import executeOrRun
from externals.checksummingTools import sha_for_file
from databaseFunctions import insertIntoEvents
import MySQLdb
from archivematicaFunctions import unicodeToStr

sys.path.append("/usr/share/archivematica/dashboard")
from main.models import File, Transfer

def updateSizeAndChecksum(fileUUID, filePath, date, eventIdentifierUUID):
    fileSize = os.path.getsize(filePath)
    checksum = str(sha_for_file(filePath))

    File.objects.filter(uuid=fileUUID).update(size=fileSize, checksum=checksum)

    insertIntoEvents(fileUUID=fileUUID, \
                     eventIdentifierUUID=eventIdentifierUUID, \
                     eventType="message digest calculation", \
                     eventDateTime=date, \
                     eventDetail="program=\"python\"; module=\"hashlib.sha256()\"", \
                     eventOutcomeDetailNote=checksum)


def addFileToTransfer(filePathRelativeToSIP, fileUUID, transferUUID, taskUUID, date, sourceType="ingestion", eventDetail="", use="original"):
    #print filePathRelativeToSIP, fileUUID, transferUUID, taskUUID, date, sourceType, eventDetail, use
    insertIntoFiles(fileUUID, filePathRelativeToSIP, date, transferUUID=transferUUID, use=use)
    insertIntoEvents(fileUUID=fileUUID, \
                   eventIdentifierUUID=taskUUID, \
                   eventType=sourceType, \
                   eventDateTime=date, \
                   eventDetail=eventDetail, \
                   eventOutcome="", \
                   eventOutcomeDetailNote="")
    addAccessionEvent(fileUUID, transferUUID, date)

def addAccessionEvent(fileUUID, transferUUID, date):
    transfer = Transfer.objects.get(uuid=transferUUID)
    if transfer.accessionid:
        eventIdentifierUUID = uuid.uuid4().__str__()
        eventOutcomeDetailNote =  "accession#" + MySQLdb.escape_string(transfer.accessionid) 
        insertIntoEvents(fileUUID=fileUUID, \
               eventIdentifierUUID=eventIdentifierUUID, \
               eventType="registration", \
               eventDateTime=date, \
               eventDetail="", \
               eventOutcome="", \
               eventOutcomeDetailNote=eventOutcomeDetailNote)
    
def addFileToSIP(filePathRelativeToSIP, fileUUID, sipUUID, taskUUID, date, sourceType="ingestion", use="original"):
    insertIntoFiles(fileUUID, filePathRelativeToSIP, date, sipUUID=sipUUID, use=use)
    insertIntoEvents(fileUUID=fileUUID, \
                   eventIdentifierUUID=taskUUID, \
                   eventType=sourceType, \
                   eventDateTime=date, \
                   eventDetail="", \
                   eventOutcome="", \
                   eventOutcomeDetailNote="")

#Used to write to file
#@output - the text to append to the file
#@fileName - The name of the file to create, or append to.
#@returns - 0 if ok, non zero if error occured.
def writeToFile(output, fileName, writeWhite=False):
    #print fileName
    if not writeWhite and output.isspace():
        return 0
    if fileName and output:
        #print "writing to: " + fileName
        if fileName.startswith("<^Not allowed to write to file^> "):
            return -1
        try:
            f = open(fileName, 'a')
            f.write(output.__str__())
            f.close()
            os.chmod(fileName, 488)
        except OSError as ose:
            print >>sys.stderr, "output Error", ose
            return -2
        except IOError as (errno, strerror):
            print "I/O error({0}): {1}".format(errno, strerror)
            return -3
    else:
        print "No output, or file specified"
    return 0

def renameAsSudo(source, destination):
    """Used to move/rename Directories that the archivematica user may or may not have writes to move"""
    command = "sudo mv \"" + source + "\"   \"" + destination + "\""
    if isinstance(command, unicode):
        command = command.encode("utf-8")
    exitCode, stdOut, stdError = executeOrRun("command", command, "", printing=False)
    if exitCode:
        print >>sys.stderr, "exitCode:", exitCode
        print >>sys.stderr, stdOut
        print >>sys.stderr, stdError
        exit(exitCode)


def updateDirectoryLocation(src, dst, unitPath, unitIdentifier, unitIdentifierType, unitPathReplaceWith):
    srcDB = src.replace(unitPath, unitPathReplaceWith)
    if not srcDB.endswith("/") and srcDB != unitPathReplaceWith:
        srcDB += "/"
    dstDB = dst.replace(unitPath, unitPathReplaceWith)
    if not dstDB.endswith("/") and dstDB != unitPathReplaceWith:
        dstDB += "/"

    kwargs = {
        "removedtime__isnull": True,
        "currentlocation__startswith": srcDB,
        unitIdentifierType: unitIdentifier
    }
    files = File.objects.filter(**kwargs)

    for f in files:
        f.currentlocation = f.currentlocation.replace(srcDB, dstDB)
        f.save()
    if os.path.isdir(dst):
        if dst.endswith("/"):
            dst += "."
        else:
            dst += "/."
    print "moving: ", src, dst
    shutil.move(src, dst)

def updateFileLocation2(src, dst, unitPath, unitIdentifier, unitIdentifierType, unitPathReplaceWith):
    """Dest needs to be the actual full destination path with filename."""
    srcDB = src.replace(unitPath, unitPathReplaceWith)
    dstDB = dst.replace(unitPath, unitPathReplaceWith)
    # Fetch the file UUID
    kwargs = {
        "removedtime__isnull": True,
        "currentlocation": srcDB,
        unitIdentifierType: unitIdentifier
    }
    files = File.objects.filter(**kwargs)
    count = files.count()
    if count != 1:
        print >> sys.stderr, 'ERROR: file information not found:', count, "rows for arguments:", repr(kwargs)
        exit(4)
    # Move the file
    print "Moving", src, 'to', dst
    shutil.move(src, dst)
    # Update the DB
    f = files.get()
    f.currentlocation = dstDB
    f.save()

def updateFileLocation(src, dst, eventType, eventDateTime, eventDetail, eventIdentifierUUID = uuid.uuid4().__str__(), fileUUID="None", sipUUID = None, transferUUID=None, eventOutcomeDetailNote = ""):
    """If the file uuid is not provided, will use the sip uuid and old path to find the file uuid"""
    src = unicodeToStr(src)
    dst = unicodeToStr(dst)
    fileUUID = unicodeToStr(fileUUID)
    if not fileUUID or fileUUID == "None":
        kwargs = {
            "removedtime__isnull": True,
            "currentlocation": src
        }

        if sipUUID:
            kwargs["sip_id"] = sipUUID
        elif transferUUID:
            kwargs["transfer_id"] = transferUUID
        else:
            raise ValueError("One of fileUUID, sipUUID, or transferUUID must be provided")

        f = File.objects.get(**kwargs)
    else:
        f = File.objects.get(uuid=fileUUID)

    if eventOutcomeDetailNote == "":
        eventOutcomeDetailNote = "Original name=\"%s\"; cleaned up name=\"%s\"" %(src, dst)
    # CREATE THE EVENT
    insertIntoEvents(fileUUID=f.uuid, eventIdentifierUUID=eventIdentifierUUID, eventType=eventType, eventDateTime=eventDateTime, eventDetail=eventDetail, eventOutcome="", eventOutcomeDetailNote=eventOutcomeDetailNote)

    # UPDATE THE CURRENT FILE PATH
    f.currentlocation = dst
    f.save()

def getFileUUIDLike(filePath, unitPath, unitIdentifier, unitIdentifierType, unitPathReplaceWith):
    """Dest needs to be the actual full destination path with filename."""
    srcDB = filePath.replace(unitPath, unitPathReplaceWith)
    kwargs = {
        "removedtime__isnull": True,
        "currentlocation__contains": srcDB,
        unitIdentifierType: unitIdentifier
    }
    return {f.currentlocation: f.uuid for f in File.objects.filter(**kwargs)}
    
def updateFileGrpUsefileGrpUUID(fileUUID, fileGrpUse, fileGrpUUID):
    File.objects.filter(uuid=fileUUID).update(filegrpuse=fileGrpUse, filegrpuuid=fileGrpUUID)

def updateFileGrpUse(fileUUID, fileGrpUse):
    File.objects.filter(uuid=fileUUID).update(filegrpuse=fileGrpUse)

def findFileInNormalizatonCSV(csv_path, commandClassification, target_file, sip_uuid):
    """ Returns the original filename or None for a manually normalized file.

    :param str csv_path: absolute path to normalization.csv
    :param str commandClassification: "access" or "preservation"
    :param str target_file: Path for access or preservation file to match against, relative to the objects directory
    :param str sip_uuid: UUID of the SIP the files belong to

    :returns: Path to the origin file for `target_file`. Note this is the path from normalization.csv, so will be the original location.
    """
    # use universal newline mode to support unusual newlines, like \r
    with open(csv_path, 'rbU') as csv_file:
        reader = csv.reader(csv_file)
        # Search CSV for an access/preservation filename that matches target_file
        # Get original name of target file, to handle sanitized names
        sql = """SELECT Files.originalLocation FROM Files WHERE removedTime = 0 AND Files.currentLocation LIKE '%{filename}' AND sipUUID='{sip_uuid}';""".format(
            filename=target_file, sip_uuid=sip_uuid)
        rows = databaseInterface.queryAllSQL(sql)
        if len(rows) != 1:
            print >>sys.stderr, "{} file ({}) not found in DB.".format(commandClassification, target_file)
            sys.exit(2)
        target_file = rows[0][0].replace('%transferDirectory%objects/', '', 1).replace('%SIPDirectory%objects/', '', 1)
        try:
            for row in reader:
                if not row:
                    continue
                if "#" in row[0]:  # ignore comments
                    continue
                original, access, preservation = row
                if commandClassification == "access" and access == target_file:
                    print "Found access file ({0}) for original ({1})".format(access, original)
                    return original
                if commandClassification == "preservation" and preservation == target_file:
                    print "Found preservation file ({0}) for original ({1})".format(preservation, original)
                    return original
            else:
                return None
        except csv.Error:
            print >>sys.stderr, "Error reading {filename} on line {linenum}".format(
                filename=csv_path, linenum=reader.line_num)
            sys.exit(2)
