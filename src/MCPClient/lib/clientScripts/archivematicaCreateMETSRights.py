#!/usr/bin/python -OO
#
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Archivematica.    If not, see <http://www.gnu.org/licenses/>.

# @package Archivematica
# @subpackage archivematicaClientScript
# @author Joseph Perry <joseph@artefactual.com>

#/src/dashboard/src/main/models.py

import sys
import uuid
import lxml.etree as etree

import archivematicaXMLNamesSpace as ns
sys.path.append("/usr/lib/archivematica/archivematicaCommon")
from countryCodes import getCodeForCountry
import databaseInterface
from sharedVariablesAcrossModules import sharedVariablesAcrossModules


def formatDate(date):
    """hack fix for 0.8, easy dashboard insertion ISO 8061 -> edtfSimpleType"""
    if date:
        date = date.replace("/", "-")
    return date


def archivematicaGetRights(metadataAppliesToList, fileUUID):
    """[(fileUUID, fileUUIDTYPE), (sipUUID, sipUUIDTYPE), (transferUUID, transferUUIDType)]"""
    ret = []
    rightsBasisActuallyOther = ["Policy", "Donor"]
    for metadataAppliesToidentifier, metadataAppliesToType in metadataAppliesToList:
        list = "RightsStatement.pk, rightsStatementIdentifierType, rightsStatementIdentifierType, rightsStatementIdentifierValue, rightsBasis, copyrightStatus, copyrightJurisdiction, copyrightStatusDeterminationDate, licenseTerms, copyrightApplicableStartDate, copyrightApplicableEndDate, licenseApplicableStartDate, licenseApplicableEndDate"
        key = list.split(", ")
        sql = """SELECT %s FROM RightsStatement LEFT JOIN RightsStatementCopyright ON RightsStatementCopyright.fkRightsStatement = RightsStatement.pk LEFT JOIN RightsStatementLicense ON RightsStatementLicense.fkRightsStatement = RightsStatement.pk WHERE metadataAppliesToidentifier = '%s' AND metadataAppliesToType = '%s';""" % (list, metadataAppliesToidentifier, metadataAppliesToType)
        rows = databaseInterface.queryAllSQL(sql)
        if not rows:
            continue
        else:
            for row in rows:
                valueDic= {}
                rightsStatement = etree.Element(ns.premisBNS + "rightsStatement", nsmap={'premis': ns.premisNS})
                rightsStatement.set(ns.xsiBNS+"schemaLocation", ns.premisNS + " http://www.loc.gov/standards/premis/v2/premis-v2-2.xsd")
                #rightsStatement.set("version", "2.1") #cvc-complex-type.3.2.2: Attribute 'version' is not allowed to appear in element 'rightsStatement'.
                ret.append(rightsStatement)
                for i in range(len(key)):
                    valueDic[key[i]] = row[i]
                
                rightsStatementIdentifier = etree.SubElement(rightsStatement, ns.premisBNS + "rightsStatementIdentifier")
                if valueDic["rightsStatementIdentifierValue"]:
                    etree.SubElement(rightsStatementIdentifier, ns.premisBNS + "rightsStatementIdentifierType").text = valueDic["rightsStatementIdentifierType"]
                    etree.SubElement(rightsStatementIdentifier, ns.premisBNS + "rightsStatementIdentifierValue").text = valueDic["rightsStatementIdentifierValue"]
                else:
                    etree.SubElement(rightsStatementIdentifier, ns.premisBNS + "rightsStatementIdentifierType").text = "UUID"
                    etree.SubElement(rightsStatementIdentifier, ns.premisBNS + "rightsStatementIdentifierValue").text = uuid.uuid4().__str__()
                if valueDic["rightsBasis"] in rightsBasisActuallyOther:
                    etree.SubElement(rightsStatement, ns.premisBNS + "rightsBasis").text = "Other"
                else:
                    etree.SubElement(rightsStatement, ns.premisBNS + "rightsBasis").text = valueDic["rightsBasis"]
                
                #copright information
                if valueDic["rightsBasis"].lower() in ["copyright"]:
                    sql = """SELECT pk, copyrightStatus, copyrightJurisdiction, copyrightStatusDeterminationDate, copyrightApplicableStartDate, copyrightApplicableEndDate, copyrightApplicableEndDateOpen FROM RightsStatementCopyright WHERE fkRightsStatement = %d""" % (valueDic["RightsStatement.pk"])
                    rows2 = databaseInterface.queryAllSQL(sql)
                    for row2 in rows2:
                        copyrightInformation = etree.SubElement(rightsStatement, ns.premisBNS + "copyrightInformation")
                        etree.SubElement(copyrightInformation, ns.premisBNS + "copyrightStatus").text = valueDic["copyrightStatus"]
                        copyrightJurisdiction = valueDic["copyrightJurisdiction"]
                        copyrightJurisdictionCode = getCodeForCountry(copyrightJurisdiction.__str__().upper())
                        if copyrightJurisdictionCode != None:
                            copyrightJurisdiction = copyrightJurisdictionCode 
                        etree.SubElement(copyrightInformation, ns.premisBNS + "copyrightJurisdiction").text = copyrightJurisdiction 
                        etree.SubElement(copyrightInformation, ns.premisBNS + "copyrightStatusDeterminationDate").text = formatDate(valueDic["copyrightStatusDeterminationDate"])
                        #copyrightNote Repeatable
                        sql = "SELECT copyrightNote FROM RightsStatementCopyrightNote WHERE fkRightsStatementCopyrightInformation = %d;" % (row2[0])
                        rows3 = databaseInterface.queryAllSQL(sql)
                        for row3 in rows3:
                            etree.SubElement(copyrightInformation, ns.premisBNS + "copyrightNote").text =  row3[0]
                            
                        #RightsStatementCopyrightDocumentationIdentifier
                        getDocumentationIdentifier(valueDic["RightsStatement.pk"], copyrightInformation)
    
                        copyrightApplicableDates = etree.SubElement(copyrightInformation, ns.premisBNS + "copyrightApplicableDates")
                        if valueDic["copyrightApplicableStartDate"]:
                            etree.SubElement(copyrightApplicableDates, ns.premisBNS + "startDate").text = formatDate(valueDic["copyrightApplicableStartDate"])
                        if row2[6]: #, copyrightApplicableEndDateOpen
                            etree.SubElement(copyrightApplicableDates, ns.premisBNS + "endDate").text = "OPEN"
                        elif valueDic["copyrightApplicableEndDate"]:
                            etree.SubElement(copyrightApplicableDates, ns.premisBNS + "endDate").text = formatDate(valueDic["copyrightApplicableEndDate"])
                
                elif valueDic["rightsBasis"].lower() in ["license"]:
                    sql = """SELECT licenseTerms, licenseApplicableStartDate, licenseApplicableEndDate,  licenseDocumentationIdentifierType, licenseDocumentationIdentifierValue, RightsStatementLicense.pk, licenseDocumentationIdentifierRole, licenseApplicableEndDateOpen
                                FROM RightsStatementLicense JOIN RightsStatementLicenseDocumentationIdentifier ON RightsStatementLicenseDocumentationIdentifier.fkRightsStatementLicense = RightsStatementLicense.pk WHERE RightsStatementLicense.fkRightsStatement = %d;""" % (valueDic["RightsStatement.pk"])
                    rows2 = databaseInterface.queryAllSQL(sql)
                    for row2 in rows2:
                        licenseInformation = etree.SubElement(rightsStatement, ns.premisBNS + "licenseInformation")
                        
                        licenseDocumentIdentifier = etree.SubElement(licenseInformation, ns.premisBNS + "licenseDocumentationIdentifier")
                        etree.SubElement(licenseDocumentIdentifier, ns.premisBNS + "licenseDocumentationIdentifierType").text = row2[3]
                        etree.SubElement(licenseDocumentIdentifier, ns.premisBNS + "licenseDocumentationIdentifierValue").text = row2[4]
                        etree.SubElement(licenseDocumentIdentifier, ns.premisBNS + "licenseDocumentationRole").text = row2[6]
                        
                        etree.SubElement(licenseInformation, ns.premisBNS + "licenseTerms").text = valueDic["licenseTerms"]
                        
                        sql = "SELECT licenseNote FROM RightsStatementLicenseNote WHERE fkRightsStatementLicense = %d;" % (row2[5])
                        rows3 = databaseInterface.queryAllSQL(sql)
                        for row3 in rows3:
                            etree.SubElement(licenseInformation, ns.premisBNS + "licenseNote").text =  row3[0]
                            
                        licenseApplicableDates = etree.SubElement(licenseInformation, ns.premisBNS + "licenseApplicableDates")
                        if valueDic["licenseApplicableStartDate"]:
                            etree.SubElement(licenseApplicableDates, ns.premisBNS + "startDate").text = formatDate(valueDic["licenseApplicableStartDate"])
                        if row2[7]: #licenseApplicableEndDateOpen
                            etree.SubElement(licenseApplicableDates, ns.premisBNS + "endDate").text = "OPEN"
                        elif valueDic["licenseApplicableEndDate"]:
                            etree.SubElement(licenseApplicableDates, ns.premisBNS + "endDate").text = formatDate(valueDic["licenseApplicableEndDate"])
                    
                elif valueDic["rightsBasis"].lower() in ["statute"]:
                    #4.1.5 statuteInformation (O, R)
                    getstatuteInformation(valueDic["RightsStatement.pk"], rightsStatement)
                    
                elif valueDic["rightsBasis"].lower() in ["donor", "policy", "other"]:
                    otherRightsInformation = etree.SubElement(rightsStatement, ns.premisBNS + "otherRightsInformation")
                    sql = """SELECT pk, otherRightsBasis, otherRightsApplicableStartDate, otherRightsApplicableEndDate, otherRightsApplicableEndDateOpen FROM RightsStatementOtherRightsInformation WHERE RightsStatementOtherRightsInformation.fkRightsStatement = %d;""" % (valueDic["RightsStatement.pk"])
                    rows2 = databaseInterface.queryAllSQL(sql)
                    for row2 in rows2:
                        #otherRightsDocumentationIdentifier
                        sql = """SELECT otherRightsDocumentationIdentifierType, otherRightsDocumentationIdentifierValue, otherRightsDocumentationIdentifierRole FROM RightsStatementOtherRightsDocumentationIdentifier WHERE fkRightsStatementotherRightsInformation = %s """ % (row2[0])
                        rows3 = databaseInterface.queryAllSQL(sql)
                        for row3 in rows3:
                            otherRightsDocumentationIdentifier = etree.SubElement(otherRightsInformation, ns.premisBNS + "otherRightsDocumentationIdentifier")
                            etree.SubElement(otherRightsDocumentationIdentifier, ns.premisBNS + "otherRightsDocumentationIdentifierType").text = row3[0]
                            etree.SubElement(otherRightsDocumentationIdentifier, ns.premisBNS + "otherRightsDocumentationIdentifierValue").text = row3[1]
                            etree.SubElement(otherRightsDocumentationIdentifier, ns.premisBNS + "otherRightsDocumentationRole").text = row3[2]
                        
                        otherRightsBasis = row2[1]
                        
                        if not otherRightsBasis or valueDic["rightsBasis"] in rightsBasisActuallyOther: #not 100%
                            otherRightsBasis = valueDic["rightsBasis"]
                        etree.SubElement(otherRightsInformation, ns.premisBNS + "otherRightsBasis").text = otherRightsBasis
                        
                        
                        otherRightsApplicableStartDate = row2[2]
                        otherRightsApplicableEndDate = row2[3]
                        otherRightsApplicableEndDateOpen = row2[4]
                        if otherRightsApplicableStartDate or otherRightsApplicableEndDate:  
                            otherRightsApplicableDates = etree.SubElement(otherRightsInformation, ns.premisBNS + "otherRightsApplicableDates")
                            if otherRightsApplicableStartDate:
                                etree.SubElement(otherRightsApplicableDates, ns.premisBNS + "startDate").text = formatDate(otherRightsApplicableStartDate)
                            if otherRightsApplicableEndDateOpen:
                                etree.SubElement(otherRightsApplicableDates, ns.premisBNS + "endDate").text = "OPEN"
                            elif otherRightsApplicableEndDate:
                                etree.SubElement(otherRightsApplicableDates, ns.premisBNS + "endDate").text = formatDate(otherRightsApplicableEndDate)
    
                        #otherRightsNote Repeatable
                        sql = "SELECT otherRightsNote FROM RightsStatementOtherRightsNote WHERE fkRightsStatementOtherRightsInformation = %d;" % (row2[0])
                        rows3 = databaseInterface.queryAllSQL(sql)
                        for row3 in rows3:
                            etree.SubElement(otherRightsInformation, ns.premisBNS + "otherRightsNote").text =  row3[0]
    
                #4.1.6 rightsGranted (O, R)
                getrightsGranted(valueDic["RightsStatement.pk"], rightsStatement)

                #4.1.7 linkingObjectIdentifier (O, R)
                linkingObjectIdentifier = etree.SubElement(rightsStatement, ns.premisBNS + "linkingObjectIdentifier")
                etree.SubElement(linkingObjectIdentifier, ns.premisBNS + "linkingObjectIdentifierType").text = "UUID"
                etree.SubElement(linkingObjectIdentifier, ns.premisBNS + "linkingObjectIdentifierValue").text = fileUUID
    return ret

def getDocumentationIdentifier(pk, parent):
    sql = "SELECT pk, copyrightDocumentationIdentifierType, copyrightDocumentationIdentifierValue, copyrightDocumentationIdentifierRole FROM RightsStatementCopyrightDocumentationIdentifier WHERE fkRightsStatementCopyrightInformation = %d" % (pk)
    rows = databaseInterface.queryAllSQL(sql)
    for row in rows:
        statuteInformation = etree.SubElement(parent, ns.premisBNS + "copyrightDocumentationIdentifier")
        etree.SubElement(statuteInformation, ns.premisBNS + "copyrightDocumentationIdentifierType").text = row[1]
        etree.SubElement(statuteInformation, ns.premisBNS + "copyrightDocumentationIdentifierValue").text = row[2]
        etree.SubElement(statuteInformation, ns.premisBNS + "copyrightDocumentationRole").text = row[3]


def getstatuteInformation(pk, parent):
    sql = "SELECT pk, statuteJurisdiction, statuteCitation, statuteInformationDeterminationDate, statuteapplicablestartdate, statuteapplicableenddate, statuteApplicableEndDateOpen FROM RightsStatementStatuteInformation WHERE fkRightsStatement = %d" % (pk)
    #print sql
    rows = databaseInterface.queryAllSQL(sql)
    for row in rows:
        statuteInformation = etree.SubElement(parent, ns.premisBNS + "statuteInformation")
        etree.SubElement(statuteInformation, ns.premisBNS + "statuteJurisdiction").text = row[1]
        etree.SubElement(statuteInformation, ns.premisBNS + "statuteCitation").text = row[2]
        etree.SubElement(statuteInformation, ns.premisBNS + "statuteInformationDeterminationDate").text = formatDate(row[3])

        #statuteNote Repeatable
        sql = "SELECT statuteNote FROM RightsStatementStatuteInformationNote WHERE fkRightsStatementStatuteInformation = %d;" % (row[0])
        rows2 = databaseInterface.queryAllSQL(sql)
        for row2 in rows2:
            etree.SubElement(statuteInformation, ns.premisBNS + "statuteNote").text =  row2[0]
        
        sql = """SELECT statuteDocumentationIdentifierType, statuteDocumentationIdentifierValue, statuteDocumentationIdentifierRole FROM RightsStatementStatuteDocumentationIdentifier WHERE fkRightsStatementStatuteInformation = %s """ % (row[0])
        rows2 = databaseInterface.queryAllSQL(sql)
        for row2 in rows2:
            statuteDocumentationIdentifier = etree.SubElement(statuteInformation, ns.premisBNS + "statuteDocumentationIdentifier")
            etree.SubElement(statuteDocumentationIdentifier, ns.premisBNS + "statuteDocumentationIdentifierType").text = row2[0]
            etree.SubElement(statuteDocumentationIdentifier, ns.premisBNS + "statuteDocumentationIdentifierValue").text = row2[1]
            etree.SubElement(statuteDocumentationIdentifier, ns.premisBNS + "statuteDocumentationRole").text = row2[2]
        
        statuteapplicablestartdate =  row[4]
        statuteapplicableenddate = row[5]
        statuteApplicableEndDateOpen = row[6]
        if statuteapplicablestartdate or statuteapplicableenddate or statuteApplicableEndDateOpen:
             statuteApplicableDates = etree.SubElement(statuteInformation, ns.premisBNS + "statuteApplicableDates")
             if statuteapplicablestartdate: 
                etree.SubElement(statuteApplicableDates, ns.premisBNS + "startDate").text = formatDate(statuteapplicablestartdate)
             if statuteApplicableEndDateOpen:
                 etree.SubElement(statuteApplicableDates, ns.premisBNS + "endDate").text = "OPEN"
             elif statuteapplicableenddate:
                 etree.SubElement(statuteApplicableDates, ns.premisBNS + "endDate").text = formatDate(statuteapplicableenddate)
        

def getrightsGranted(pk, parent):
    sql = "SELECT RightsStatementRightsGranted.pk, act, startDate, endDate, endDateOpen FROM RightsStatementRightsGranted  WHERE fkRightsStatement = %d" % (pk)
    rows = databaseInterface.queryAllSQL(sql)
    for row in rows:
        rightsGranted = etree.SubElement(parent, ns.premisBNS + "rightsGranted")
        etree.SubElement(rightsGranted, ns.premisBNS + "act").text = row[1]
        
        restriction = "Undefined"
        sql = """SELECT restriction FROM RightsStatementRightsGrantedRestriction WHERE RightsStatementRightsGrantedRestriction.fkRightsStatementRightsGranted = %s """ % (row[0])
        rows2 = databaseInterface.queryAllSQL(sql)
        for row2 in rows2:
            restriction = row2[0]
            if not restriction.lower() in ["disallow", "conditional", "allow"]:
                print >>sys.stderr, "The value of element restriction must be: 'Allow', 'Disallow', or 'Conditional':", restriction
                sharedVariablesAcrossModules.globalErrorCount +=1
            etree.SubElement(rightsGranted, ns.premisBNS + "restriction").text = restriction
        
        if row[2] or row[3] or row[4]:
            if restriction.lower() in ["allow"]:
                termOfGrant = etree.SubElement(rightsGranted, ns.premisBNS + "termOfGrant")
            elif restriction.lower() in ["disallow", "conditional"]:
                termOfGrant = etree.SubElement(rightsGranted, ns.premisBNS + "termOfRestriction")
            else:
                print >>sys.stderr, "The value of element restriction must be: 'Allow', 'Dissallow', or 'Conditional'"
                sharedVariablesAcrossModules.globalErrorCount +=1
                continue
        
            if row[2]:
                etree.SubElement(termOfGrant, ns.premisBNS + "startDate").text = formatDate(row[2])
            if row[4]:
                etree.SubElement(termOfGrant, ns.premisBNS + "endDate").text = "OPEN"
            elif row[3]:
                etree.SubElement(termOfGrant, ns.premisBNS + "endDate").text = formatDate(row[3])
        
        #4.1.6.4 rightsGrantedNote (O, R)
        sql = "SELECT rightsGrantedNote FROM RightsStatementRightsGrantedNote WHERE fkRightsStatementRightsGranted = %d;" % (row[0])
        rows2 = databaseInterface.queryAllSQL(sql)
        for row2 in rows2:
            etree.SubElement(rightsGranted, ns.premisBNS + "rightsGrantedNote").text =  row2[0]
