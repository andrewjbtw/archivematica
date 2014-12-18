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
import uuid
import shutil
import os
import sys

sys.path.append("/usr/share/archivematica/dashboard")
from main.models import File

sys.path.append("/usr/lib/archivematica/archivematicaCommon")
import databaseFunctions
from archivematicaCreateStructuredDirectory import createStructuredDirectory

if __name__ == '__main__':
    while False:
        import time
        time.sleep(10)
    objectsDirectory = sys.argv[1]
    transferName = sys.argv[2]
    transferUUID = sys.argv[3]
    processingDirectory = sys.argv[4]
    autoProcessSIPDirectory = sys.argv[5]
    sharedPath = sys.argv[6]

    for container in os.listdir(objectsDirectory):
        sipUUID = uuid.uuid4().__str__()
        containerPath = os.path.join(objectsDirectory, container)
        if not os.path.isdir(containerPath):
            print >>sys.stderr, "file (not container) found: ", container
            continue
            
        sipName = "%s-%s" % (transferName, container) 
        
        tmpSIPDir = os.path.join(processingDirectory, sipName) + "/"
        destSIPDir =  os.path.join(autoProcessSIPDirectory, sipName) + "/"
        createStructuredDirectory(tmpSIPDir, createManualNormalizedDirectories=True)
        databaseFunctions.createSIP(destSIPDir.replace(sharedPath, '%sharedPath%'), sipUUID)
    
        # move the objects to the SIPDir
        for item in os.listdir(containerPath):
            shutil.move(os.path.join(containerPath, item), os.path.join(tmpSIPDir, "objects", item))
    
        # get the database list of files in the objects directory
        # for each file, confirm it's in the SIP objects directory, and update the current location/ owning SIP'
        dir = '%transferDirectory%objects/' + container
        files = File.objects.filter(removedtime__isnull=True,
                                    currentlocation__startswith=dir,
                                    transfer_id=transferUUID)
        for f in files:
            currentPath = databaseFunctions.deUnicode(f.currentlocation).replace('%transferDirectory%objects/' + container, '%transferDirectory%objects')
            currentSIPFilePath = currentPath.replace("%transferDirectory%", tmpSIPDir)
            if os.path.isfile(currentSIPFilePath):
                f.currentlocation = currentPath.replace("%transferDirectory%", "%SIPDirectory%")
                f.sip_id = sipUUID
                f.save()
            else:
                print >>sys.stderr, "file not found: ", currentSIPFilePath

        # moveSIPTo autoProcessSIPDirectory
        shutil.move(tmpSIPDir, destSIPDir)
    