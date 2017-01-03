#!/usr/bin/env python
# _*_ coding:utf-8 _*_

"""
Project-wide application configuration.

DO NOT STORE SECRETS, PASSWORDS, ETC. IN THIS FILE.
They will be exposed to users. Use environment variables instead.
See get_secrets() below for a fast way to access them.
"""

import logging
import os

from authomatic.providers import oauth2
from authomatic import Authomatic


"""
NAMES
"""
# Project name to be used in urls
# Use dashes, not underscores!
PROJECT_SLUG = 'liveblog'

# Project name to be used in file paths
PROJECT_FILENAME = 'liveblog'

# The name of the repository containing the source
REPOSITORY_NAME = 'liveblog'
GITHUB_USERNAME = 'nprapps'
REPOSITORY_URL = 'git@github.com:%s/%s.git' % (
    GITHUB_USERNAME, REPOSITORY_NAME)
REPOSITORY_ALT_URL = None  # 'git@bitbucket.org:nprapps/%s.git' % REPOSITORY_NAME'

# Project name used for assets rig
# Should stay the same, even if PROJECT_SLUG changes
ASSETS_SLUG = 'liveblog'


# DEPLOY SETUP CONFIG
LIVEBLOG_DIRECTORY_PREFIX = 'liveblogs/'
CURRENT_LIVEBLOG = 'inauguration-liveblog-20170120'
SEAMUS_ID = ''  # SEAMUS PAGE ID FOR DEEP LINKING
try:
    from local_settings import CURRENT_LIVEBLOG
    # Override SEAMUS_ID to generate the sharing list accordingly
    from local_settings import SEAMUS_ID
except ImportError:
    pass

"""
DEPLOYMENT
"""
PRODUCTION_S3_BUCKET = 'apps.npr.org'

STAGING_S3_BUCKET = 'stage-apps.npr.org'

ASSETS_S3_BUCKET = 'assets.apps.npr.org'

ARCHIVE_S3_BUCKET = 'election-backup.apps.npr.org'

DEFAULT_MAX_AGE = 20

RELOAD_TRIGGER = False
RELOAD_CHECK_INTERVAL = 60

PRODUCTION_SERVERS = ['52.87.183.57']
STAGING_SERVERS = ['52.87.228.251']

# Should code be deployed to the web/cron servers?
DEPLOY_TO_SERVERS = True

SERVER_USER = 'ubuntu'
SERVER_PYTHON = 'python2.7'
SERVER_PROJECT_PATH = '/home/%s/apps/%s' % (SERVER_USER, PROJECT_FILENAME)
SERVER_REPOSITORY_PATH = '%s/repository' % SERVER_PROJECT_PATH
SERVER_VIRTUALENV_PATH = '%s/virtualenv' % SERVER_PROJECT_PATH

# Should the crontab file be installed on the servers?
# If True, DEPLOY_TO_SERVERS must also be True
DEPLOY_CRONTAB = False

# Should the service configurations be installed on the servers?
# If True, DEPLOY_TO_SERVERS must also be True
DEPLOY_SERVICES = False

UWSGI_SOCKET_PATH = '/tmp/%s.uwsgi.sock' % PROJECT_FILENAME

# Services are the server-side services we want to enable and configure.
# A three-tuple following this format:
# (service name, service deployment path, service config file extension)
SERVER_SERVICES = [
    ('deploy', '/etc/init', 'conf'),
]

# These variables will be set at runtime. See configure_targets() below
S3_BUCKET = None
S3_BASE_URL = None
S3_DEPLOY_URL = None
SERVERS = []
SERVER_BASE_URL = None
SERVER_LOG_PATH = None
DEBUG = True
LOG_LEVEL = None

"""
TEST AUTOINIT LOADER
"""
AUTOINIT_LOADER = False

"""
COPY EDITING
"""
COPY_GOOGLE_DOC_KEY = '1Oizr_i1SizfvrwPfU9sSbxa4ktIXCh5q5mR4bksoouM'
COPY_PATH = 'data/copy.xlsx'

LIVEBLOG_HTML_PATH = 'data/liveblog.html'
LIVEBLOG_BACKUP_PATH = 'data/liveblog_backup.pickle'
LOAD_COPY_INTERVAL = 10
SPONSORSHIP_POSITION = -1  # -1 disables
NUM_HEADLINE_POSTS = 3

"""
GOOGLE APPS SCRIPTS
"""

GAS_LOG_KEY = '1mwmMYtllwOhZi5Q8SeDppZQx7QoqXjU7lKuJAuu1qcY' # Google app script logs spreadsheet key
LIVEBLOG_GDOC_KEY = '1jLWACDn2EA9KOqQj4AgCQWjPoXze28hsyaxHP9Il3h0' # Google doc key
SCRIPT_PROJECT_NAME = 'liveblog' # Google app scripts project name
SEAMUS_ID = '500427835'


"""
SHARING
"""
SHARE_URL = 'http://%s/%s%s/' % (PRODUCTION_S3_BUCKET,
                                 LIVEBLOG_DIRECTORY_PREFIX,
                                 CURRENT_LIVEBLOG)


"""
SERVICES
"""
NPR_GOOGLE_ANALYTICS = {
    'ACCOUNT_ID': 'UA-5828686-4',
    'DOMAIN': PRODUCTION_S3_BUCKET,
    'TOPICS': ''  # e.g. '[1014,3,1003,1002,1001]'
}

VIZ_GOOGLE_ANALYTICS = {
    'ACCOUNT_ID': 'UA-5828686-75'
}

"""
MONGODB
"""
MONGODB_URL = 'mongodb://localhost:27017/'
DB_IMAGE_TTL = 60 * 5
DB_TWEET_TTL = 60 * 2

"""
OAUTH
"""

GOOGLE_OAUTH_CREDENTIALS_PATH = '~/.google_oauth_credentials'

authomatic_config = {
    'google': {
        'id': 1,
        'class_': oauth2.Google,
        'consumer_key': os.environ.get('GOOGLE_OAUTH_CLIENT_ID'),
        'consumer_secret': os.environ.get('GOOGLE_OAUTH_CONSUMER_SECRET'),
        'scope': ['https://www.googleapis.com/auth/drive',
                  'https://www.googleapis.com/auth/userinfo.email',
                  'https://www.googleapis.com/auth/drive.scripts',
                  'https://www.googleapis.com/auth/documents',
                  'https://www.googleapis.com/auth/script.external_request',
                  'https://www.googleapis.com/auth/script.scriptapp',
                  'https://www.googleapis.com/auth/script.send_mail',
                  'https://www.googleapis.com/auth/script.storage',
                  'https://www.googleapis.com/auth/spreadsheets'],
        'offline': True,
    },
}

authomatic = Authomatic(authomatic_config, os.environ.get('AUTHOMATIC_SALT'))

"""
Logging
"""
LOG_FORMAT = '%(levelname)s:%(name)s:%(asctime)s: %(message)s'

"""
Utilities
"""


def get_secrets():
    """
    A method for accessing our secrets.
    """
    secrets_dict = {}

    for k, v in os.environ.items():
        if k.startswith(PROJECT_SLUG):
            k = k[len(PROJECT_SLUG) + 1:]
            secrets_dict[k] = v

    return secrets_dict


def configure_targets(deployment_target):
    """
    Configure deployment targets. Abstracted so this can be
    overriden for rendering before deployment.
    """
    global S3_BUCKET
    global S3_BASE_URL
    global S3_DEPLOY_URL
    global SERVERS
    global SERVER_BASE_URL
    global SERVER_LOG_PATH
    global DEBUG
    global DEPLOYMENT_TARGET
    global LOG_LEVEL
    global ASSETS_MAX_AGE
    global LIVEBLOG_GDOC_KEY
    global SEAMUS_ID
    global BOP_EMBED_URL

    if deployment_target == 'production':
        S3_BUCKET = PRODUCTION_S3_BUCKET
        S3_BASE_URL = '//%s/%s%s' % (S3_BUCKET,
                                     LIVEBLOG_DIRECTORY_PREFIX,
                                     CURRENT_LIVEBLOG)
        S3_DEPLOY_URL = 's3://%s/%s%s' % (S3_BUCKET,
                                          LIVEBLOG_DIRECTORY_PREFIX,
                                          CURRENT_LIVEBLOG)
        SERVERS = PRODUCTION_SERVERS
        SERVER_BASE_URL = '//%s/%s' % (SERVERS[0], PROJECT_SLUG)
        SERVER_LOG_PATH = '/var/log/%s' % PROJECT_FILENAME
        LOG_LEVEL = logging.INFO
        DEBUG = False
        ASSETS_MAX_AGE = 86400
        SEAMUS_ID = '500427835'
        # Production google_apps_scripts > staging > elections16-liveblog
        # ELECTIONS16 LIVEBLOG PRODUCTION Elections16 > LiveBlog
        LIVEBLOG_GDOC_KEY = '10VW8FfWLu5pyKeDqHawagsqQ4cETdwVmWRyeNAKKWyk'
        # Dress rehearsal google_apps_scripts > staging > elections16-liveblog
        # LIVEBLOG_GDOC_KEY = '1EJToRyjX0K1hQ8DPA2_MK9rKmOkIazsVHWPhfOotX88'
        # Monday - day before test google_apps_scripts > staging > elections16-liveblog
        # LIVEBLOG_GDOC_KEY = '1RhLApNcdqVkg4s7wxstaZ_EbrFqwEXCjDoKrULQJIaY'
    elif deployment_target == 'staging':
        S3_BUCKET = STAGING_S3_BUCKET
        S3_BASE_URL = '//%s/%s%s' % (S3_BUCKET,
                                     LIVEBLOG_DIRECTORY_PREFIX,
                                     CURRENT_LIVEBLOG)
        S3_DEPLOY_URL = 's3://%s/%s%s' % (S3_BUCKET,
                                          LIVEBLOG_DIRECTORY_PREFIX,
                                          CURRENT_LIVEBLOG)
        SERVERS = STAGING_SERVERS
        SERVER_BASE_URL = 'http://%s/%s' % (SERVERS[0], PROJECT_SLUG)
        SERVER_LOG_PATH = '/var/log/%s' % PROJECT_FILENAME
        LOG_LEVEL = logging.INFO
        DEBUG = True
        ASSETS_MAX_AGE = 20
        SEAMUS_ID = '500306012'
        # Staging google_apps_scripts > staging > elections16-liveblog
        LIVEBLOG_GDOC_KEY = '1NRH2bDm2cWG4yQDdznkHG4q-xI-zGYjqdZKbWjl9EtM'
        # Dress rehearsal google_apps_scripts > staging > elections16-liveblog
        # LIVEBLOG_GDOC_KEY = '1EJToRyjX0K1hQ8DPA2_MK9rKmOkIazsVHWPhfOotX88'
        # ELECTIONS16 LIVEBLOG PRODUCTION Elections16 > LiveBlog
        #LIVEBLOG_GDOC_KEY = '10VW8FfWLu5pyKeDqHawagsqQ4cETdwVmWRyeNAKKWyk'
    else:
        S3_BUCKET = None
        S3_BASE_URL = 'http://127.0.0.1:8000'
        S3_DEPLOY_URL = None
        SERVERS = []
        SERVER_BASE_URL = 'http://127.0.0.1:8001/%s' % PROJECT_SLUG
        SERVER_LOG_PATH = '/tmp'
        LOG_LEVEL = logging.INFO
        DEBUG = True
        ASSETS_MAX_AGE = 20

        # Development google_apps_scripts > dev > elections16-liveblog
        # > Elections16-Liveblog - Development
        # LIVEBLOG_GDOC_KEY = '1jLWACDn2EA9KOqQj4AgCQWjPoXze28hsyaxHP9Il3h0'
        # Development google_apps_scripts > dev > ParserTest
        # LIVEBLOG_GDOC_KEY = '1m0mQYsgNgMOJe6CZ9dpPbAjSe3R5o0U7UHogguwzPuo'
        # LIVEBLOG_GDOC_KEY = '10-SF-5UWgQqfbAmV3v4k9V6IGmYlPdSLQUUmHMj_zck'
        # Development google_apps_scripts > dev > Refactoring
        LIVEBLOG_GDOC_KEY = '1EJToRyjX0K1hQ8DPA2_MK9rKmOkIazsVHWPhfOotX88'
        try:
            from local_settings import LIVEBLOG_GDOC_KEY, S3_BASE_URL
        except ImportError:
            pass

    DEPLOYMENT_TARGET = deployment_target

"""
Run automated configuration
"""
DEPLOYMENT_TARGET = os.environ.get('DEPLOYMENT_TARGET', None)

configure_targets(DEPLOYMENT_TARGET)
