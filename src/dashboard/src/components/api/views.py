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

# stdlib, alphabetical
import json
import os

# Core Django, alphabetical
from django.db.models import Q
import django.http

# External dependencies, alphabetical
from annoying.functions import get_object_or_None
from tastypie.authentication import ApiKeyAuthentication

# This project, alphabetical
from contrib.mcp.client import MCPClient
from components import helpers
from main import models


TRANSFER_TYPE_DIRECTORIES = {
    'standard': 'standardTransfer',
    'unzipped bag': 'baggitDirectory',
    'zipped bag': 'baggitZippedDirectory',
    'dspace': 'Dspace',
    'maildir': 'maildir',
    'TRIM': 'TRIM'
}


def authenticate_request(request):
    error = None

    api_auth = ApiKeyAuthentication()
    authorized = api_auth.is_authenticated(request)

    if authorized:
        client_ip = request.META['REMOTE_ADDR']
        whitelist = helpers.get_setting('api_whitelist', '127.0.0.1').split()
        # logging.debug('client IP: %s, whitelist: %s', client_ip, whitelist)
        if client_ip not in whitelist:
            error = 'Host/IP ' + client_ip + ' not authorized.'
    else:
        error = 'API key not valid.'

    return error


def get_unit_status(unit_uuid, unit_type):
    """
    Get status for a SIP or Transfer.

    Returns a tuple of (status, SIP UUID).

    Status is one of FAILED, REJECTED, USER_INPUT, COMPLETE or PROCESSING.

    SIP UUID is populated only if the unit_type was unitTransfer and status is
    COMPLETE.  Otherwise, it is None.

    :param str unit_uuid: UUID of the SIP or Transfer
    :param str unit_type: unitSIP or unitTransfer
    :return: Tuple (status, SIP UUID or None)
    """
    sip_uuid = None
    job = models.Job.objects.filter(sipuuid=unit_uuid).filter(unittype=unit_type).order_by('-createdtime', '-createdtimedec')[0]
    if job.currentstep == 'Awaiting decision':
        status = 'USER_INPUT'
    elif 'failed' in job.microservicegroup.lower():
        status = 'FAILED'
    elif 'reject' in job.microservicegroup.lower():
        status = 'REJECTED'
    elif job.jobtype == 'Remove the processing directory':  # Done storing AIP
        status = 'COMPLETE'
    elif models.Job.objects.filter(sipuuid=unit_uuid).filter(jobtype='Create SIP from transfer objects').exists():
        status = 'COMPLETE'
        # Get SIP UUID
        sips = models.File.objects.filter(transfer_id=unit_uuid).values('sip').distinct()
        if sips:
            sip_uuid = sips[0]['sip']
        else:
            sip_uuid = None
    elif models.Job.objects.filter(sipuuid=unit_uuid).filter(jobtype='Move transfer to backlog').exists():
        status = 'COMPLETE'
        sip_uuid = 'BACKLOG'
    else:
        status = 'PROCESSING'

    return status, sip_uuid


def status(request, unit_uuid, unit_type):
    # Example: http://127.0.0.1/api/transfer/status/?username=mike&api_key=<API key>
    if request.method not in ('GET',):
        return django.http.HttpResponseNotAllowed(['GET'])
    auth_error = authenticate_request(request)
    response = {}
    if auth_error is not None:
        response = {'message': auth_error, 'error': True}
        return django.http.HttpResponseForbidden(
            json.dumps(response),
            mimetype='application/json'
        )
    error = None

    # Get info about unit
    if unit_type == 'unitTransfer':
        unit = get_object_or_None(models.Transfer, uuid=unit_uuid)
    elif unit_type == 'unitSIP':
        unit = get_object_or_None(models.SIP, uuid=unit_uuid)

    if unit is None:
        response['message'] = 'Cannot fetch {} with UUID {}'.format(unit_type, unit_uuid)
        response['error'] = True
        return django.http.HttpResponseBadRequest(
            json.dumps(response),
            mimetype='application/json',
        )
    directory = unit.currentpath if unit_type == 'unitSIP' else unit.currentlocation
    response['directory'] = os.path.basename(os.path.normpath(directory))
    response['name'] = response['directory'].replace('-' + unit_uuid, '', 1)
    response['uuid'] = unit_uuid

    # Get status
    status, sip_uuid = get_unit_status(unit_uuid, unit_type)
    response['status'] = status
    if sip_uuid:
        response['sip_uuid'] = sip_uuid

    if error is not None:
        response['message'] = error
        response['error'] = True
        return django.http.HttpResponseServerError(
            json.dumps(response),
            mimetype='application/json'
        )
    response['message'] = 'Fetched status for {} successfully.'.format(unit_uuid)
    return helpers.json_response(response)


def waiting_for_user_input(request):
    # Example: http://127.0.0.1/api/transfer/waiting?username=mike&api_key=<API key>
    if request.method not in ('GET',):
        return django.http.HttpResponseNotAllowed(['GET'])

    auth_error = authenticate_request(request)
    response = {}
    if auth_error is not None:
        response = {'message': auth_error, 'error': True}
        return django.http.HttpResponseForbidden(
            json.dumps(response),
            mimetype='application/json'
        )

    error = None
    waiting_units = []

    jobs = models.Job.objects.filter(currentstep='Awaiting decision')
    for job in jobs:
        unit_uuid = job.sipuuid
        directory = os.path.basename(os.path.normpath(job.directory))
        unit_name = directory.replace('-' + unit_uuid, '', 1)

        waiting_units.append({
            'sip_directory': directory,
            'sip_uuid': unit_uuid,
            'sip_name': unit_name,
            'microservice': job.jobtype,
            # 'choices': []  # TODO? Return list of choices, see ingest.views.ingest_status
        })

    response['results'] = waiting_units

    if error is not None:
        response['message'] = error
        response['error'] = True
        return django.http.HttpResponseServerError(
            json.dumps(response),
            mimetype='application/json'
        )
    response['message'] = 'Fetched transfers successfully.'
    return helpers.json_response(response)


def unapproved_transfers(request):
    # Example: http://127.0.0.1/api/transfer/unapproved?username=mike&api_key=<API key>
    if request.method == 'GET':
        auth_error = authenticate_request(request)

        response = {}

        if auth_error is None:
            error = None
            unapproved = []

            jobs = models.Job.objects.filter(
                (
                    Q(jobtype="Approve standard transfer")
                    | Q(jobtype="Approve DSpace transfer")
                    | Q(jobtype="Approve bagit transfer")
                    | Q(jobtype="Approve zipped bagit transfer")
                ) & Q(currentstep='Awaiting decision')
            )

            for job in jobs:
                # remove standard transfer path from directory (and last character)
                type_and_directory = job.directory.replace(
                    get_modified_standard_transfer_path() + '/',
                    '',
                    1
                )

                # remove trailing slash if not a zipped bag file
                if not helpers.file_is_an_archive(job.directory):
                    type_and_directory = type_and_directory[:-1]

                transfer_watch_directory = type_and_directory.split('/')[0]
                # Get transfer type from transfer directory
                transfer_type_directories_reversed = {v: k for k, v in TRANSFER_TYPE_DIRECTORIES.iteritems()}
                transfer_type = transfer_type_directories_reversed[transfer_watch_directory]

                job_directory = type_and_directory.replace(transfer_watch_directory + '/', '', 1)

                unapproved.append({
                    'type': transfer_type,
                    'directory': job_directory,
                    'uuid': job.sipuuid,
                })

            # get list of unapproved transfers
            # return list as JSON
            response['results'] = unapproved

            if error is not None:
                response['message'] = error
                response['error'] = True
            else:
                response['message'] = 'Fetched unapproved transfers successfully.'

                if error is not None:
                    return django.http.HttpResponseServerError(
                        json.dumps(response),
                        mimetype='application/json'
                    )
                else:
                    return helpers.json_response(response)
        else:
            response['message'] = auth_error
            response['error'] = True
            return django.http.HttpResponseForbidden(
                json.dumps(response),
                mimetype='application/json'
            )
    else:
        return django.http.HttpResponseNotAllowed(['GET'])


def approve_transfer(request):
    # Example: curl --data \
    #   "username=mike&api_key=<API key>&directory=MyTransfer" \
    #   http://127.0.0.1/api/transfer/approve
    if request.method == 'POST':
        auth_error = authenticate_request(request)

        response = {}

        if auth_error is None:
            error = None

            directory = request.POST.get('directory', '')
            transfer_type = request.POST.get('type', 'standard')
            error, unit_uuid = approve_transfer_via_mcp(directory, transfer_type, request.user.id)

            if error is not None:
                response['message'] = error
                response['error'] = True
                return django.http.HttpResponseServerError(
                    json.dumps(response),
                    mimetype='application/json'
                )
            else:
                response['message'] = 'Approval successful.'
                response['uuid'] = unit_uuid
                return helpers.json_response(response)
        else:
            response['message'] = auth_error
            response['error'] = True
            return django.http.HttpResponseForbidden(
                json.dumps(response),
                mimetype='application/json'
            )
    else:
        return django.http.HttpResponseNotAllowed(['POST'])


def get_modified_standard_transfer_path(transfer_type=None):
    path = os.path.join(
        helpers.get_server_config_value('watchDirectoryPath'),
        'activeTransfers'
    )

    if transfer_type is not None:
        try:
            path = os.path.join(path, TRANSFER_TYPE_DIRECTORIES[transfer_type])
        except:
            return None

    shared_directory_path = helpers.get_server_config_value('sharedDirectory')
    return path.replace(shared_directory_path, '%sharedPath%', 1)


def approve_transfer_via_mcp(directory, transfer_type, user_id):
    error = None
    unit_uuid = None
    if (directory != ''):
        # assemble transfer path
        modified_transfer_path = get_modified_standard_transfer_path(transfer_type)

        if modified_transfer_path is None:
            error = 'Invalid transfer type.'
        else:
            if transfer_type == 'zipped bag':
                transfer_path = os.path.join(modified_transfer_path, directory)
            else:
                transfer_path = os.path.join(modified_transfer_path, directory, '')
            # look up job UUID using transfer path
            try:
                job = models.Job.objects.filter(directory=transfer_path, currentstep='Awaiting decision')[0]
                unit_uuid = job.sipuuid

                type_task_config_descriptions = {
                    'standard': 'Approve standard transfer',
                    'unzipped bag': 'Approve bagit transfer',
                    'zipped bag': 'Approve zipped bagit transfer',
                    'dspace': 'Approve DSpace transfer',
                    'maildir': 'Approve maildir transfer',
                    'TRIM': 'Approve TRIM transfer'
                }

                type_description = type_task_config_descriptions[transfer_type]

                # use transfer type to fetch possible choices to execute
                task = models.TaskConfig.objects.get(description=type_description)
                link = models.MicroServiceChainLink.objects.get(currenttask=task.pk)
                choices = models.MicroServiceChainChoice.objects.filter(choiceavailableatlink=link.pk)

                # attempt to find appropriate choice
                chain_to_execute = None
                for choice in choices:
                    if choice.chainavailable.description == 'Approve transfer':
                        chain_to_execute = choice.chainavailable.pk

                # execute choice if found
                if chain_to_execute is not None:
                    client = MCPClient()
                    client.execute(job.pk, chain_to_execute, user_id)
                else:
                    error = 'Error: could not find MCP choice to execute.'

            except Exception:
                error = 'Unable to find unapproved transfer directory.'
                # logging.exception(error)

    else:
        error = 'Please specify a transfer directory.'

    return error, unit_uuid
