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
# @subpackage MCPServer
# @author Joseph Perry <joseph@artefactual.com>

from unit import unit
from unitFile import unitFile
import archivematicaMCP
import os
import sys
sys.path.append("/usr/lib/archivematica/archivematicaCommon")
import databaseInterface
from dicts import ReplacementDict
import lxml.etree as etree


class unitDIP(unit):

    def __init__(self, currentPath, UUID):
        self.currentPath = currentPath.__str__()
        self.UUID = UUID
        self.fileList = {}
        self.owningUnit = None

    def reloadFileList(self):
        self.fileList = {}
        currentPath = self.currentPath.replace("%sharedPath%", \
                                               archivematicaMCP.config.get('MCPServer', "sharedDirectory"), 1) + "/"
        for directory, subDirectories, files in os.walk(currentPath):
            directory = directory.replace( currentPath, "%SIPDirectory%", 1)
            for file in files:
                filePath = os.path.join(directory, file)
                self.fileList[filePath] = unitFile(filePath)

        sql = """SELECT  fileUUID, currentLocation FROM Files WHERE sipUUID =  '""" + self.UUID + "'" #AND Files.removedTime = 0; TODO
        c, sqlLock = databaseInterface.querySQL(sql)
        row = c.fetchone()
        while row != None:
            UUID = row[0]
            currentPath = row[1]
            if currentPath in self.fileList:
                self.fileList[currentPath].UUID = UUID
            else:
                print "todo: find deleted files/exclude"
                print row[99]#fail
            row = c.fetchone()
            self.fileList[filePath].UUID = UUID
        sqlLock.release()




    def reload(self):
        pass


    def getReplacementDic(self, target):
        ret = ReplacementDict.frommodel(
            type_='sip',
            sip=self.UUID
        )
        ret["%unitType%"] = "DIP"
        return ret

    def xmlify(self):
        ret = etree.Element("unit")
        etree.SubElement(ret, "type").text = "DIP"
        unitXML = etree.SubElement(ret, "unitXML")
        etree.SubElement(unitXML, "UUID").text = self.UUID
        etree.SubElement(unitXML, "currentPath").text = self.currentPath.replace(archivematicaMCP.config.get('MCPServer', "sharedDirectory"), "%sharedPath%")
        return ret
