#!/usr/bin/python -OO
#
# This file is part of Archivematica.
#
# Copyright 2010-2012 Artefactual Systems Inc. <http://artefactual.com>
#
# Archivematica is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Archivematica is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Archivematica.    If not, see <http://www.gnu.org/licenses/>.

# @package Archivematica
# @subpackage archivematicaClientScript
# @author Joseph Perry <joseph@artefactual.com>
# @version svn: $Id$

#/src/dashboard/src/main/models.py


import os
import sys
import csv
import traceback
sys.path.append("/usr/lib/archivematica/archivematicaCommon")
from sharedVariablesAcrossModules import sharedVariablesAcrossModules

simpleMetadataCSVkey = []
simpleMetadataCSV = {}
compoundMetadataCSVkey = []
compoundMetadataCSV = {}


CSVMetadata = (simpleMetadataCSVkey, simpleMetadataCSV,
               compoundMetadataCSVkey, compoundMetadataCSV)


def parseMetadata(SIPPath):
    # Parse the metadata.csv files from the transfers
    transfersPath = os.path.join(SIPPath, "objects", "metadata", "transfers")
    if not os.path.isdir(transfersPath):
        return
    for transfer in os.listdir(transfersPath):
        metadataCSVFilePath = os.path.join(transfersPath,
                                           transfer, "metadata.csv")
        if os.path.isfile(metadataCSVFilePath):
            try:
                parseMetadataCSV(metadataCSVFilePath)
            except Exception:
                print >>sys.stderr, "error parsing: ", metadataCSVFilePath
                traceback.print_exc(file=sys.stderr)
                sharedVariablesAcrossModules.globalErrorCount += 1
    # Parse the SIP's metadata.csv if it exists
    metadataCSVFilePath = os.path.join(SIPPath, 'objects', 'metadata', 'metadata.csv')
    if os.path.isfile(metadataCSVFilePath):
        try:
            parseMetadataCSV(metadataCSVFilePath)
        except Exception:
            print >>sys.stderr, "error parsing: ", metadataCSVFilePath
            traceback.print_exc(file=sys.stderr)
            sharedVariablesAcrossModules.globalErrorCount += 1


def parseMetadataCSV(metadataCSVFilePath):
    # use universal newline mode to support unusual newlines, like \r
    with open(metadataCSVFilePath, 'rbU') as f:
        reader = csv.reader(f)
        firstRow = True
        type = ""
        for row in reader:
            if firstRow:  # header row
                type = row[0].lower()
                if type == "filename":
                    simpleMetadataCSVkey.extend(row)
                elif type == "parts":
                    compoundMetadataCSVkey.extend(row)
                else:
                    print >>sys.stderr, "error parsing: ", metadataCSVFilePath
                    print >>sys.stderr, "unsupported: ", type
                    sharedVariablesAcrossModules.globalErrorCount += 1
                    return
                firstRow = False

            else:  # data row
                if type == "filename":
                    simpleMetadataCSV[row[0]] = row
                elif type == "parts":
                    directory = row[0]
                    if directory.endswith("/"):
                        directory = directory[:-1]
                    compoundMetadataCSV[directory] = row
    global CSVMetadata
    return CSVMetadata


if __name__ == '__main__':
    parseMetadata(sys.argv[1])
