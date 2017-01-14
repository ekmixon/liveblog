#!/usr/bin/env python
# _*_ coding:utf-8 _*_

from datetime import datetime
import json
import os

from boto.s3.key import Key
from fabric.api import local, require, settings, task, execute
from fabric.state import env
from termcolor import colored

import app_config

# Other fabfiles
import assets
import daemons
import data
import flat
import gs
import issues
import render
import text
import utils
import spreadsheet
import logging

logging.basicConfig(format=app_config.LOG_FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(app_config.LOG_LEVEL)

if app_config.DEPLOY_TO_SERVERS:
    import servers

if app_config.DEPLOY_CRONTAB:
    import cron_jobs

# Bootstrap can only be run once, then it's disabled
if app_config.PROJECT_SLUG == '$NEW_PROJECT_SLUG':
    import bootstrap

"""
Base configuration
"""
env.user = app_config.SERVER_USER
env.forward_agent = True

env.hosts = []

"""
Environments

Changing environment requires a full-stack test.
An environment points to both a server and an S3
bucket.
"""
@task
def production():
    """
    Run as though on production.
    """
    env.settings = 'production'
    app_config.configure_targets(env.settings)
    env.hosts = app_config.SERVERS

@task
def staging():
    """
    Run as though on staging.
    """
    env.settings = 'staging'
    app_config.configure_targets(env.settings)
    env.hosts = app_config.SERVERS

@task
def development():
    """
    Run as though on staging.
    """
    env.settings = 'development'
    app_config.configure_targets(env.settings)
    env.hosts = app_config.SERVERS

"""
Branches

Changing branches requires deploying that branch to a host.
"""
@task
def stable():
    """
    Work on stable branch.
    """
    env.branch = 'stable'

@task
def master():
    """
    Work on development branch.
    """
    env.branch = 'master'

@task
def branch(branch_name):
    """
    Work on any specified branch.
    """
    env.branch = branch_name

"""
Running the app
"""
@task
def app(port='8000'):
    """
    Serve app.py.
    """

    gunicorn = 'gunicorn -b 0.0.0.0:%s --timeout 3600 --debug --reload --log-file=logs/app.log app:wsgi_app' % port

    if env.get('settings'):
        local("DEPLOYMENT_TARGET=%s bash -c 'gunicorn -b 0.0.0.0:%s --timeout 3600 --debug --reload --log-file=logs/app.log app:wsgi_app'" % (env.settings, port))
    else:
        local('concurrently "%s" "npm start"' % gunicorn)

@task
def public_app(port='8001'):
    """
    Serve public_app.py.
    """
    if env.get('settings'):
        local("DEPLOYMENT_TARGET=%s bash -c 'gunicorn -b 0.0.0.0:%s --timeout 3600 --debug --reload --log-file=logs/public_app.log public_app:wsgi_app'" % (env.settings, port))
    else:
        local('concurrently "%s" "npm start"' % gunicorn)

@task
def tests():
    """
    Run Python unit tests.
    """
    local('nosetests')

"""
Deployment

Changes to deployment requires a full-stack test. Deployment
has two primary functions: Pushing flat files to S3 and deploying
code to a remote server if required.
"""
@task
def update():
    """
    Update all application data not in repository (copy, assets, etc).
    """
    utils.install_font(force=False)
    text.update()
    assets.sync()
    data.update()

@task
def deploy(remote='origin', reload=False):
    """
    Deploy the latest app to S3 and, if configured, to our servers.
    """
    require('settings', provided_by=[production, staging])

    if app_config.DEPLOY_TO_SERVERS:
        require('branch', provided_by=[stable, master, branch])

        if (app_config.DEPLOYMENT_TARGET == 'production' and env.branch != 'stable'):
            utils.confirm(
                colored("You are trying to deploy the '%s' branch to production.\nYou should really only deploy a stable branch.\nDo you know what you're doing?" % env.branch, "red")
            )

        servers.checkout_latest(remote)

        servers.fabcast('text.update')
        #servers.fabcast('assets.sync')
        #servers.fabcast('data.update')

        if app_config.DEPLOY_CRONTAB:
            servers.install_crontab()

        if app_config.DEPLOY_SERVICES:
            servers.deploy_confs()
    else:
        utils.confirm(colored("You are trying to deploy a static liveblog to production S3 bucket %s%s Doc Key: %s.\nDo you know what you're doing?" %
                              (app_config.LIVEBLOG_DIRECTORY_PREFIX,
                               app_config.CURRENT_LIVEBLOG,
                               app_config.LIVEBLOG_GDOC_KEY), "red"))
    update()
    render.render_all()

    # Clear files that should never be deployed
    local('rm -rf www/live-data')

    flat.deploy_folder(
        app_config.S3_BUCKET,
        'www',
        '%s%s' % (app_config.LIVEBLOG_DIRECTORY_PREFIX,
                  app_config.CURRENT_LIVEBLOG),
        headers={
            'Cache-Control': 'max-age=%i' % app_config.DEFAULT_MAX_AGE
        },
        ignore=['www/assets/*', 'www/live-data/*']
    )

    flat.deploy_folder(
        app_config.S3_BUCKET,
        'www/assets',
        '%s%s/assets' % (app_config.LIVEBLOG_DIRECTORY_PREFIX,
                         app_config.CURRENT_LIVEBLOG),
        headers={
            'Cache-Control': 'max-age=%i' % app_config.ASSETS_MAX_AGE
        }
    )

    # DEPLOY STATIC LIVEBLOG FROM LOCAL ENVIRONMENT
    if app_config.DEPLOY_STATIC_LIVEBLOG:
        execute('deploy_liveblog')

    if reload:
        reset_browsers()

    if not check_timestamp():
        reset_browsers()


@task
def deploy_liveblog():
    """
    Renders and deploys the liveblog and preview html
    """
    require('settings', provided_by=[production, staging])

    render.render_liveblog()
    flat.deploy_folder(
        app_config.S3_BUCKET,
        '.liveblog',
        '%s%s' % (app_config.LIVEBLOG_DIRECTORY_PREFIX,
                  app_config.CURRENT_LIVEBLOG),
        headers={
            'Cache-Control': 'max-age=%i' % app_config.DEFAULT_MAX_AGE
        }
    )

    if app_config.DEPLOYMENT_TARGET == 'production':
        execute('deploy_liveblog_backup')


@task
def deploy_liveblog_backup():
    """
    deploy to our backup S3 bucket election-backup.apps.npr.org
    """
    now = datetime.now().strftime('%Y-%m-%d-%H:%M:%S')

    flat.deploy_folder(
        app_config.ARCHIVE_S3_BUCKET,
        '.liveblog',
        'liveblogs/%s/%s-%s' % (app_config.CURRENT_LIVEBLOG,
                                now, app_config.PROJECT_SLUG),
        headers={
            'Cache-Control': 'max-age=%i' % app_config.DEFAULT_MAX_AGE
        }
    )


@task
def deploy_server(remote='origin'):
    """
    Deploy code to our servers and restart daemons.
    """
    require('settings', provided_by=[production, staging])

    # Pull latest code
    if app_config.DEPLOY_TO_SERVERS:
        require('branch', provided_by=[stable, master, branch])

        if (app_config.DEPLOYMENT_TARGET == 'production' and env.branch != 'stable'):
            utils.confirm(
                colored("You are trying to deploy the '%s' branch to production.\nYou should really only deploy a stable branch.\nDo you know what you're doing?" % env.branch, "red")
            )

        servers.checkout_latest(remote)
    # Restart daemon service
    servers.restart_service('deploy')


@task
def cp_backup_folder(folder):
    """
    Copies copydoc.html to the frontend folder
    """
    require('settings', provided_by=[production])
    if not folder:
        print "you need to provide one of the backup folder names to copy from"
        exit()
    else:
        utils.confirm(
            colored("You are trying to copy an old backup version of the liveblog to the production app\nDo you know what you're doing?", "red")
        )
        cmd = 'aws s3 cp --acl public-read s3://election-backup.apps.npr.org/liveblog/%s/ %s/ --recursive' % (folder, app_config.S3_DEPLOY_URL)
        local(cmd)


@task
def check_timestamp():
    require('settings', provided_by=[production, staging])

    bucket = utils.get_bucket(app_config.S3_BUCKET)
    k = Key(bucket)
    k.key = '%s/live-data/timestamp.json' % app_config.PROJECT_SLUG
    if k.exists():
        return True
    else:
        return False

@task
def reset_browsers():
    """
    Deploy a timestamp so the client will reset their page. For bugfixes
    """
    require('settings', provided_by=[production, staging])

    if not os.path.exists('www/live-data'):
        os.makedirs('www/live-data')

    payload = {}
    now = datetime.now().strftime('%s')
    payload['timestamp'] = now

    with open('www/live-data/timestamp.json', 'w') as f:
        json.dump(payload, f)

    flat.deploy_folder(
        app_config.S3_BUCKET,
        'www/live-data',
        '%s/live-data' % app_config.PROJECT_SLUG,
        headers={
            'Cache-Control': 'max-age=%i' % app_config.DEFAULT_MAX_AGE
        }
    )

"""
Destruction

Changes to destruction require setup/deploy to a test host in order to test.
Destruction should remove all files related to the project from both a remote
host and S3.
"""

@task
def shiva_the_destroyer():
    """
    Deletes the app from s3
    """
    require('settings', provided_by=[production, staging])

    utils.confirm(
        colored("You are about to destroy everything deployed to %s for this project.\nDo you know what you're doing?')" % app_config.DEPLOYMENT_TARGET, "red")
    )

    with settings(warn_only=True):
        current_folder = '%s%s' % (app_config.LIVEBLOG_DIRECTORY_PREFIX,
                                   app_config.CURRENT_LIVEBLOG)
        flat.delete_folder(app_config.S3_BUCKET, current_folder)

        if app_config.DEPLOY_TO_SERVERS:
            servers.delete_project()

            if app_config.DEPLOY_CRONTAB:
                servers.uninstall_crontab()

            if app_config.DEPLOY_SERVICES:
                servers.nuke_confs()
