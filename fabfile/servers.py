# _*_ coding:utf-8 _*_
#!/usr/bin/env python

"""
Commands work with servers. (Hiss, boo.)
"""

import copy
import logging

from fabric.api import local, put, settings, require, run, sudo, task
from fabric.state import env
from jinja2 import Template

import app_config

logging.basicConfig(format=app_config.LOG_FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(app_config.LOG_LEVEL)

"""
Setup
"""

@task
def setup():
    """
    Setup servers for deployment.

    This does not setup services or push to S3. Run deploy() next.
    """
    require('settings', provided_by=['production', 'staging'])
    require('branch', provided_by=['stable', 'master', 'branch'])

    if not app_config.DEPLOY_TO_SERVERS:
        logger.error('You must set DEPLOY_TO_SERVERS = True in your app_config.py before setting up the servers.')

        return

    install_google_oauth_creds()
    create_directories()
    create_virtualenv()
    clone_repo()
    checkout_latest()
    install_requirements()
    setup_logs()

def create_directories():
    """
    Create server directories.
    """
    require('settings', provided_by=['production', 'staging'])

    run('mkdir -p %(SERVER_PROJECT_PATH)s' % app_config.__dict__)
    # run('mkdir -p /var/www/uploads/%(PROJECT_FILENAME)s' % app_config.__dict__)

def create_virtualenv():
    """
    Setup a server virtualenv.
    """
    require('settings', provided_by=['production', 'staging'])

    run('virtualenv -p %(SERVER_PYTHON)s %(SERVER_VIRTUALENV_PATH)s' % app_config.__dict__)
    run('source %(SERVER_VIRTUALENV_PATH)s/bin/activate' % app_config.__dict__)

def clone_repo():
    """
    Clone the source repository.
    """
    require('settings', provided_by=['production', 'staging'])

    run('git clone %(REPOSITORY_URL)s %(SERVER_REPOSITORY_PATH)s' % app_config.__dict__)

    if app_config.REPOSITORY_ALT_URL:
        run('git remote add bitbucket %(REPOSITORY_ALT_URL)s' % app_config.__dict__)

@task
def checkout_latest(remote='origin'):
    """
    Checkout the latest source.
    """
    require('settings', provided_by=['production', 'staging'])
    require('branch', provided_by=['stable', 'master', 'branch'])

    run(f'cd {app_config.SERVER_REPOSITORY_PATH}; git fetch {remote}')
    run(
        f'cd {app_config.SERVER_REPOSITORY_PATH}; git checkout {env.branch}; git pull {remote} {env.branch}'
    )

@task
def install_requirements():
    """
    Install the latest requirements.
    """
    require('settings', provided_by=['production', 'staging'])

    run('%(SERVER_VIRTUALENV_PATH)s/bin/pip install -r %(SERVER_REPOSITORY_PATH)s/requirements.txt' % app_config.__dict__)
    # sudo('cd %(SERVER_REPOSITORY_PATH)s; npm install' % app_config.__dict__)
    # sudo('chown -R ubuntu:ubuntu %(SERVER_REPOSITORY_PATH)s/node_modules' % app_config.__dict__)

@task
def setup_logs():
    """
    Create log directories.
    """
    require('settings', provided_by=['production', 'staging'])

    sudo('mkdir %(SERVER_LOG_PATH)s' % app_config.__dict__)
    sudo('chown ubuntu:ubuntu %(SERVER_LOG_PATH)s' % app_config.__dict__)

@task
def install_crontab():
    """
    Install cron jobs script into cron.d.
    """
    require('settings', provided_by=['production', 'staging'])

    sudo('cp %(SERVER_REPOSITORY_PATH)s/crontab /etc/cron.d/%(PROJECT_FILENAME)s' % app_config.__dict__)

@task
def uninstall_crontab():
    """
    Remove a previously install cron jobs script from cron.d
    """
    require('settings', provided_by=['production', 'staging'])

    sudo('rm /etc/cron.d/%(PROJECT_FILENAME)s' % app_config.__dict__)

@task
def install_google_oauth_creds():
    """
    Install Google Oauth credentials file (global) from workinprivate repo
    """
    run('git clone git@github.com:nprapps/workinprivate.git /tmp/workinprivate-tmp')
    run(
        f'cp /tmp/workinprivate-tmp/.google_oauth_credentials {app_config.GOOGLE_OAUTH_CREDENTIALS_PATH}'
    )

    run('rm -Rf /tmp/workinprivate-tmp')

@task
def remove_google_oauth_creds():
    """
    Remove Google oauth credentials file (global)
    """
    run(f'rm {app_config.GOOGLE_OAUTH_CREDENTIALS_PATH}')

def delete_project():
    """
    Remove the project directory. Invoked by shiva.
    """
    run('rm -rf %(SERVER_PROJECT_PATH)s' % app_config.__dict__)

"""
Configuration
"""

def _get_template_conf_path(service, extension):
    """
    Derive the path for a conf template file.
    """
    return f'confs/{service}.{extension}'

def _get_rendered_conf_path(service, extension):
    """
    Derive the rendered path for a conf file.
    """
    return f'confs/rendered/{app_config.PROJECT_FILENAME}.{service}.{extension}'

def _get_installed_conf_path(service, remote_path, extension):
    """
    Derive the installed path for a conf file.
    """
    return f'{remote_path}/{app_config.PROJECT_FILENAME}.{service}.{extension}'

def _get_installed_service_name(service):
    """
    Derive the init service name for an installed service.
    """
    return f'{app_config.PROJECT_FILENAME}.{service}'

@task
def render_confs():
    """
    Renders server configurations.
    """
    require('settings', provided_by=['production', 'staging'])

    with settings(warn_only=True):
        local('mkdir confs/rendered')

    # Copy the app_config so that when we load the secrets they don't
    # get exposed to other management commands
    context = copy.copy(app_config.__dict__)
    context.update(app_config.get_secrets())

    for service, remote_path, extension in app_config.SERVER_SERVICES:
        template_path = _get_template_conf_path(service, extension)
        rendered_path = _get_rendered_conf_path(service, extension)

        with open(template_path,  'r') as read_template:

            with open(rendered_path, 'wb') as write_template:
                payload = Template(read_template.read())
                write_template.write(payload.render(**context))

@task
def deploy_confs():
    """
    Deploys rendered server configurations to the specified server.
    This will reload nginx and the appropriate uwsgi config.
    """
    require('settings', provided_by=['production', 'staging'])

    render_confs()

    with settings(warn_only=True):
        for service, remote_path, extension in app_config.SERVER_SERVICES:
            rendered_path = _get_rendered_conf_path(service, extension)
            installed_path = _get_installed_conf_path(service, remote_path, extension)

            a = local(f'md5 -q {rendered_path}', capture=True)
            b = run(f'md5sum {installed_path}').split()[0]

            if a != b:
                logging.info(f'Updating {installed_path}')
                put(rendered_path, installed_path, use_sudo=True)

                if service == 'nginx':
                    sudo('service nginx reload')
                elif service == 'uwsgi':
                    service_name = _get_installed_service_name(service)
                    sudo('initctl reload-configuration')
                    sudo(f'service {service_name} restart')
                elif service == 'app':
                    run(f'touch {app_config.UWSGI_SOCKET_PATH}')
                    sudo(f'chmod 644 {app_config.UWSGI_SOCKET_PATH}')
                    sudo(f'chown www-data:www-data {app_config.UWSGI_SOCKET_PATH}')
            else:
                logging.info(f'{rendered_path} has not changed')

@task
def nuke_confs():
    """
    DESTROYS rendered server configurations from the specified server.
    This will reload nginx and stop the uwsgi config.
    """
    require('settings', provided_by=['production', 'staging'])

    for service, remote_path, extension in app_config.SERVER_SERVICES:
        with settings(warn_only=True):
            installed_path = _get_installed_conf_path(service, remote_path, extension)

            sudo(f'rm -f {installed_path}')

            if service == 'nginx':
                sudo('service nginx reload')
            elif service == 'uwsgi':
                service_name = _get_installed_service_name(service)
                sudo(f'service {service_name} stop')
                sudo('initctl reload-configuration')
            elif service == 'app':
                sudo(f'rm {app_config.UWSGI_SOCKET_PATH}')

@task
def start_service(service):
    """
    Start a service on the server.
    """
    require('settings', provided_by=['production', 'staging'])
    service_name = _get_installed_service_name(service)
    sudo(f'service {service_name} start')


@task
def stop_service(service):
    """
    Stop a service on the server
    """
    require('settings', provided_by=['production', 'staging'])
    service_name = _get_installed_service_name(service)
    sudo(f'service {service_name} stop')


@task
def restart_service(service):
    """
    Start a service on the server.
    """
    require('settings', provided_by=['production', 'staging'])
    service_name = _get_installed_service_name(service)
    sudo(f'service {service_name} restart')


"""
Fabcasting
"""

@task
def fabcast(command):
    """
    Actually run specified commands on the server specified
    by staging() or production().
    """
    require('settings', provided_by=['production', 'staging'])

    if not app_config.DEPLOY_TO_SERVERS:
        logging.error('You must set DEPLOY_TO_SERVERS = True in your app_config.py and setup a server before fabcasting.')

    run(
        f'cd {app_config.SERVER_REPOSITORY_PATH} && bash run_on_server.sh fab $DEPLOYMENT_TARGET branch:{env.branch} {command}'
    )
