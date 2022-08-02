#!/usr/bin/env python

import app_config
import datetime
import json
import logging
import static

from flask import Flask, make_response, render_template
from render_utils import make_context, smarty_filter, urlencode_filter
from werkzeug.debug import DebuggedApplication

app = Flask(__name__)
app.debug = app_config.DEBUG

logging.basicConfig(format=app_config.LOG_FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(app_config.LOG_LEVEL)

try:
    file_handler = logging.FileHandler(
        f'{app_config.SERVER_LOG_PATH}/public_app.log'
    )

    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
except IOError:
    logger.warn(
        f'Could not open {app_config.SERVER_LOG_PATH}/public_app.log, skipping file-based logging'
    )


app.logger.setLevel(logging.INFO)

app.register_blueprint(static.static, url_prefix=f'/{app_config.PROJECT_SLUG}')

app.add_template_filter(smarty_filter, name='smarty')
app.add_template_filter(urlencode_filter, name='urlencode')

# Example application views
@app.route(f'/{app_config.PROJECT_SLUG}/test/', methods=['GET'])
def _test_app():
    """
    Test route for verifying the application is running.
    """
    app.logger.info('Test URL requested.')

    return make_response(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

# Example of rendering index.html with public_app
@app.route(f'/{app_config.PROJECT_SLUG}/', methods=['GET'])
def index():
    """
    Example view rendering a simple page.
    """
    context = make_context(asset_depth=1)

    with open('data/featured.json') as f:
        context['featured'] = json.load(f)

    return make_response(render_template('index.html', **context))

# Enable Werkzeug debug pages
wsgi_app = DebuggedApplication(app, evalex=False) if app_config.DEBUG else app
# Catch attempts to run the app directly
if __name__ == '__main__':
    logger.error('This command has been removed! Please run "fab public_app" instead!')
