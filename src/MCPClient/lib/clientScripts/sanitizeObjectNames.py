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
# @subpackage archivematicaClientScript
# @author Joseph Perry <joseph@artefactual.com>
import sys
import subprocess
import os
import MySQLdb
import uuid
sys.path.append("/usr/lib/archivematica/archivematicaCommon")
import databaseInterface
from databaseFunctions import insertIntoEvents
from fileOperations import updateFileLocation
from archivematicaFunctions import unicodeToStr
import sanitizeNames

if __name__ == '__main__':
    objectsDirectory = sys.argv[1] #the directory to run sanitization on.
    sipUUID =  sys.argv[2]
    date = sys.argv[3]
    taskUUID = sys.argv[4]
    groupType = sys.argv[5]
    groupType = "%%%s%%" % (groupType)
    groupSQL = sys.argv[6]
    sipPath =  sys.argv[7] #the unit path
    groupID = sipUUID

    #relativeReplacement = "%sobjects/" % (groupType) #"%SIPDirectory%objects/"
    relativeReplacement = objectsDirectory.replace(sipPath, groupType, 1) #"%SIPDirectory%objects/"


    sanitizations = sanitizeNames.sanitizeRecursively(objectsDirectory)

    eventDetail= "program=\"sanitizeNames\"; version=\"" + sanitizeNames.VERSION + "\""
    for oldfile, newfile in sanitizations:
        if os.path.isfile(newfile):
            oldfile = oldfile.replace(objectsDirectory, relativeReplacement, 1)
            newfile = newfile.replace(objectsDirectory, relativeReplacement, 1)
            print oldfile, " -> ", newfile

            if groupType == "%SIPDirectory%":
                updateFileLocation(oldfile, newfile, "name cleanup", date, "prohibited characters removed:" + eventDetail, fileUUID=None, sipUUID=sipUUID)
            elif groupType == "%transferDirectory%":
                updateFileLocation(oldfile, newfile, "name cleanup", date, "prohibited characters removed:" + eventDetail, fileUUID=None, transferUUID=sipUUID)
            else:
                print >>sys.stderr, "bad group type", groupType
                exit(3)

        elif os.path.isdir(newfile):
            oldfile = oldfile.replace(objectsDirectory, relativeReplacement, 1) + "/"
            newfile = newfile.replace(objectsDirectory, relativeReplacement, 1) + "/"
            directoryContents = []

            sql = "SELECT fileUUID, currentLocation FROM Files WHERE Files.removedTime = 0 AND Files.currentLocation LIKE '" + MySQLdb.escape_string(oldfile.replace("\\", "\\\\")).replace("%","\%") + "%' AND " + groupSQL + " = '" + groupID + "';"

            c, sqlLock = databaseInterface.querySQL(sql)
            row = c.fetchone()
            while row != None:
                fileUUID = row[0]
                oldPath = row[1]
                newPath = unicodeToStr(oldPath).replace(oldfile, newfile, 1)
                directoryContents.append((fileUUID, oldPath, newPath))
                row = c.fetchone()
            sqlLock.release()

            print oldfile, " -> ", newfile

            for fileUUID, oldPath, newPath in directoryContents:
                updateFileLocation(oldPath, newPath, "name cleanup", date, "prohibited characters removed:" + eventDetail, fileUUID=fileUUID)
