#!/usr/bin/env python

"""
Commands that ease the interaction with the app google spreadsheet
"""
import app_config
import logging
import json
import os
import glob
from fabric.api import task, require
from urllib import urlencode
from utils import prep_bool_arg, check_credentials
from fabric.api import prompt


logging.basicConfig(format=app_config.LOG_FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(app_config.LOG_LEVEL)

UPLOAD_URL_TPL = 'https://www.googleapis.com/upload/drive/v2/files'
DRIVE_API_URL = 'https://www.googleapis.com/drive/v2/files'
GS_QUERY_URL = "%s?q=mimeType='application/vnd.google-apps.script'" % (DRIVE_API_URL)
MIMETYPE = 'application/vnd.google-apps.script+json'

EXTS = {
    'js': 'server_js',
    'html': 'html',
}

TYPES = {v: k for k, v in EXTS.items()}

@task
def get_doc_permissions(id=None):
    """
    get google doc permissions
    """

    require('settings', provided_by=['production', 'staging', 'development'])
    # Get the script id from the script name and deployment target
    # prioritize passed in parameters
    if not id:
        id = app_config.LIVEBLOG_GDOC_KEY

    url = f"{DRIVE_API_URL}/{id}/permissions"
    kwargs = {
        'credentials': check_credentials(),
        'url': url,
        'method': 'GET'
    }

    resp = send_api_request(kwargs)

    if resp.status == 200:
        with open('data/dict_permissions.txt', 'w') as f:
            for permission in resp.data['items']:
                try:
                    logger.info(f'Permission: {permission}')
                    extraRoles = permission['additionalRoles']
                    f.write("%s,%s\n" % (
                        permission['emailAddress'], ",".join(extraRoles)))
                except KeyError:
                    try:
                        f.write("%s,%s\n" % (
                            permission['emailAddress'], permission['role']))
                    except KeyError:
                        pass

    else:
        logger.error(f'Error ({resp.status}).')


def get_gas_project_id(name):
    """
    gets the project id from the supplied name
    """
    url = "%s and title='%s'" % (GS_QUERY_URL, name)
    kwargs = {
        'credentials': check_credentials(),
        'url': url,
        'method': 'GET'
    }

    resp = send_api_request(kwargs)

    if resp.status == 200:
        return extract_id(resp)
    elif resp.status == 403:
        resp = send_api_request(kwargs, retry=True)
        if resp.status == 200:
            return extract_id(resp)
        else:
            logger.error(f'Error ({resp.status}).')
    else:
        logger.error(f'Error ({resp.status}).')
    return None


def get_folder_id(name):
    """
    gets the project id from the supplied name
    """
    FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'
    query = "title = '%s' and mimeType = '%s' and '%s' in parents" % (
        name,
        FOLDER_MIME_TYPE,
        app_config.PARENT_FOLDER_ID)

    fields = {
        'q': query,
        'pageSize': 1,
        'spaces': 'drive'
    }
    params = urlencode(fields)
    url = f"{DRIVE_API_URL}?{params}"
    kwargs = {
        'credentials': check_credentials(),
        'url': url,
        'method': 'GET'
    }

    resp = send_api_request(kwargs)

    if resp.status == 200:
        return extract_id(resp)
    elif resp.status == 403:
        resp = send_api_request(kwargs, retry=True)
        if resp.status == 200:
            return extract_id(resp)
        else:
            logger.error(f'Error ({resp.status}).')
    else:
        logger.error(f'Error ({resp.status}).')
    return None


def extract_id(resp):
    """
    extracts the id from the API response
    """
    id = None
    if (len(resp.data['items']) == 0):
        logger.error('Project not found. '
                     'Double check the provided name and try again')
    elif (len(resp.data['items']) > 1):
        print len(resp.data['items'])
        logger.error('More than one project in the returned results.'
                     'maybe change the name to be unique?')
    else:
        id = resp.data['items'][0]['id']
    return id


@task
def list_projects(owner=None):
    """
    List all the google projects on your drive, pass owner to filter out
    """
    if (owner):
        url = "%s and '%s' in owners" % (GS_QUERY_URL, owner)
    else:
        url = GS_QUERY_URL

    kwargs = {
        'credentials': check_credentials(),
        'url': url,
        'method': 'GET'
    }

    resp = send_api_request(kwargs)

    if resp.status == 200:
        display_list_projects_results(resp)
    elif resp.status == 403:
        resp = send_api_request(kwargs, retry=True)
        if resp.status == 200:
            display_list_projects_results(resp)
        else:
            logger.error(f'Error ({resp.status}).')
    else:
        logger.error(f'Error ({resp.status}).')


def display_list_projects_results(resp):
    """
    display the results of the list projects API
    """
    for f in resp.data['items']:
        for f in resp.data['items']:
            logger.info(f"Found resource {f['title']} id: {f['id']}")
            logger.info(
                f"Download url: {f['exportLinks']['application/vnd.google-apps.script+json']}"
            )


@task
def get_project_metadata(name=None, verbose=False):
    """
    Get a google app project metadata, pass the id of the project
    """
    # Parse boolean fabric args
    verbose = prep_bool_arg(verbose)

    name = name or app_config.PROJECT_SLUG

    id = get_gas_project_id(name)

    if not id:
        exit()
    url = f'{DRIVE_API_URL}/{id}'

    kwargs = {
        'credentials': check_credentials(),
        'url': url,
        'method': 'GET'
    }

    resp = send_api_request(kwargs)

    if resp.status == 200:
        display_project_metadata_results(resp, verbose)
    elif resp.status == 403:
        resp = send_api_request(kwargs, retry=True)
        if resp.status == 200:
            display_project_metadata_results(resp, verbose)
        else:
            logger.error(f'Error ({resp.status}).')
    else:
        logger.error(f'Error ({resp.status}).')


def display_project_metadata_results(resp, verbose):
    """
    display the results of the project metadata API
    """
    logger.info(
        f"Download url: {resp.data['exportLinks']['application/vnd.google-apps.script+json']}"
    )

    if verbose:
        logger.info(f'File Resource: {resp.content}')


@task
def get_project_files(name=None):
    """
    Get all files in a given google apps script project
    """
    credentials = check_credentials()

    name = name or app_config.PROJECT_SLUG

    id = get_gas_project_id(name)

    if not id:
        exit()
    url = f'{DRIVE_API_URL}/{id}'

    kwargs = {
        'credentials': credentials,
        'url': url,
        'method': 'GET'
    }

    resp = send_api_request(kwargs)
    if resp.status == 200:
        url = resp.data['exportLinks'][MIMETYPE]
    elif resp.status == 403:
        resp = send_api_request(kwargs, retry=True)
        if resp.status == 200:
            url = resp.data['exportLinks'][MIMETYPE]
        else:
            logger.error(f'Error ({resp.status}).')
            exit()
    else:
        logger.error(f'Error ({resp.status}).')
        exit()

    if not url:
        logger.error(f'Did not find download url for {id}')
        exit()

    kwargs = {
        'credentials': credentials,
        'url': url,
        'method': 'GET'
    }

    resp = send_api_request(kwargs)
    if resp.status == 200:
        return get_project_files_results(resp)
    else:
        logger.error(f'Error ({resp.status}).')


def get_project_files_results(resp):
    """
    get the project files API results
    """
    files_found = {}
    for obj in resp.data['files']:
        if obj['type'] == 'server_js':
            ext = 'js'
        elif obj['type'] == 'html':
            ext = 'html'
        else:
            continue
        key = f"{obj['name']}.{ext}"
        files_found[key] = obj
    return files_found

@task
def download(name=None, dest='google_apps_scripts'):
    """
    Download existing project files,
    pass the id of the project and a destination path
    """

    name = name or app_config.PROJECT_SLUG
    existing_files = get_project_files(name)
    for k, v in existing_files.iteritems():
        with open(f'{dest}/{k}', "w") as f:
            f.write(v['source'])


@task
def upsert(script_name=None, src='google_apps_scripts'):
    """
    Upload project files to drive,
    pass the id of the project and a source path
    """
    require('settings', provided_by=['production', 'staging', 'development'])

    if not script_name:
        script_name = f'{app_config.DEPLOYMENT_TARGET}-{app_config.PROJECT_SLUG}'
        if app_config.DEPLOYMENT_TARGET == "production":
            script_name = app_config.PROJECT_SLUG

    id = get_gas_project_id(script_name)

    if not id:
        exit()

    existing_files = get_project_files(script_name)

    files_to_upload = [
        f for f in glob.glob(f'{src}/*') if f.split('.')[-1] in EXTS.keys()
    ]


    payload = {
        "files": []
    }

    for file_path in files_to_upload:
        key = os.path.basename(file_path)
        file_name, ext = key.split('.')
        try:
            file_type = EXTS[ext]
        except KeyError:
            continue

        try:
            file_to_upload = {
                'id': existing_files[key]['id']
            }
            logger.info(f" - Replace {key} (id={existing_files[key]['id']}) with {key}.")
        except KeyError:
            logger.info(f' - New file {key} found.')
            logger.info(f"No existing file found for {key}.")
            file_to_upload = {}

        with open(file_path) as fp:
            file_contents = fp.read()

        file_to_upload |= {
            'name': file_name,
            'type': file_type,
            'source': file_contents,
        }


        payload['files'].append(file_to_upload)

    logger.info(f"Uploading {len(payload['files'])} files... ")

    # Prepare API request
    kwargs = {
        'credentials': check_credentials(),
        'url': f'{UPLOAD_URL_TPL}/{id}',
        'method': 'PUT',
        'headers': {'Content-Type': 'application/vnd.google-apps.script+json'},
        'body': json.dumps(payload),
    }


    resp = send_api_request(kwargs)

    if resp.status == 200:
        logger.info('Done.')
    else:
        if resp.status == 403:
            resp = send_api_request(kwargs, retry=True)
            if resp.status == 200:
                logger.info('Done.')
                exit()
        logger.error(f'Error ({resp.status}).')


@task
def create(name=None, folderid=None, folder=None, src='google_apps_scripts'):
    """
    Create a new google apps script project
    """

    # Get existing project files in drive
    dest_folder_id = None
    name = name or app_config.PROJECT_SLUG

    files_to_upload = [
        f for f in glob.glob(f'{src}/*') if f.split('.')[-1] in EXTS.keys()
    ]


    if folderid:
        dest_folder_id = folderid

    elif folder:
        dest_folder_id = get_folder_id(folder)
        if not dest_folder_id:
            logger.error('Did not find the given folder, you need to create it first')
            exit()
    payload = {
        "files": []
    }

    for file_path in files_to_upload:
        key = os.path.basename(file_path)
        file_name, ext = key.split('.')
        try:
            file_type = EXTS[ext]
        except KeyError:
            continue

        with open(file_path) as fp:
            file_contents = fp.read()

        file_to_upload = {} | {
            'name': file_name,
            'type': file_type,
            'source': file_contents,
        }

        payload['files'].append(file_to_upload)

    logger.info(f"Uploading {len(payload['files'])} files... ")

    # Prepare API request
    kwargs = {
        'credentials': check_credentials(),
        'url': f'{UPLOAD_URL_TPL}?convert=true',
        'method': 'POST',
        'headers': {'Content-Type': 'application/vnd.google-apps.script+json'},
        'body': json.dumps(payload),
    }


    resp = send_api_request(kwargs)

    if resp.status == 200:
        id = resp.data['id']
        if not id:
            logger.error('did not get an id for the new project')
            exit()
        src_folder_id = resp.data['parents'][0]['id']
        success = update_metadata(id, name, src_folder_id, dest_folder_id)
        logger.info('Done.')
    else:
        if resp.status == 403:
            resp = send_api_request(kwargs, retry=True)
            if resp.status == 200:
                logger.info('Done.')
                exit()
        logger.error(f'Error ({resp.status}).')


def update_metadata(id, name, src_folder_id, dest_folder_id):
    """
    update metadata for newly created gas projects
    """

    fields = {
        'removeParents': f'{src_folder_id}',
        'addParents': f'{dest_folder_id}',
    }

    params = urlencode(fields)
    url = f"{DRIVE_API_URL}/{id}?{params}"

    # Compose payload
    payload = {
        'title': name,
    }

    kwargs = {
        'credentials': check_credentials(),
        'url': url,
        'method': 'PATCH',
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(payload)
    }

    resp = send_api_request(kwargs)

    return resp.status == 200


@task
def execute_setup(script_name=None, doc_id=None, log_id=None):
    """
    execute script setup: params script_id, document_id, log_id
    """

    require('settings', provided_by=['production', 'staging', 'development'])

    # Get secrets
    secrets = app_config.get_secrets()
    verb8tm_srt_url = secrets.get('VERB8TM_SRT_API',
                                  app_config.PROJECT_SLUG)
    verb8tm_timestamp_url = secrets.get('VERB8TM_TIMESTAMP_API',
                                        app_config.PROJECT_SLUG)

    # Get the script id from the script name and deployment target
    # prioritize passed in parameters
    if not script_name:
        script_name = '%s_%s' % (app_config.DEPLOYMENT_TARGET,
                                 app_config.SCRIPT_PROJECT_NAME)

    script_id = get_gas_project_id(script_name)

    URL_PREFIX = 'https://script.googleapis.com/v1/scripts/'

    # url
    url = '%s%s:run' % (URL_PREFIX, script_id)

    # Compose payload we pass documentID and logID to setup script properties
    payload = {
        'function': 'setup',
        'parameters': [verb8tm_srt_url,
                       verb8tm_timestamp_url,
                       app_config.LIVEBLOG_GDOC_KEY,
                       app_config.GAS_LOG_KEY]
    }

    kwargs = {
        'credentials': check_credentials(),
        'url': url,
        'method': 'POST',
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(payload)
    }

    resp = send_api_request(kwargs)

    if resp.status == 200:
        return True
    else:
        print resp.status
        exit()
    return False


def send_api_request(kwargs, retry=False):
    """
    Prompt user for confirmation, erase credentials and reauthenticate
    Returns the authomatic response
    """
    # Refresh the credentials scope and retry
    if retry:
        message = 'Forbidden response. Want to update the credentials & retry?'
        answer = prompt(message, default="No")
        if answer.lower() not in ('y', 'yes', 'buzz off', 'screw you'):
            logger.info('Ok so no retry...bye')
            exit()
        path = os.path.expanduser(app_config.GOOGLE_OAUTH_CREDENTIALS_PATH)
        os.remove(path)
        kwargs['credentials'] = check_credentials()
    logger.debug(f'API Request: {kwargs} ')
    resp = app_config.authomatic.access(**kwargs)
    logger.debug(f'API Response: {resp.content} ')
    return resp
