#!/usr/bin/env python
"""
Example application views.

Note that `render_template` is wrapped with `make_response` in all application
routes. While not necessary for most Flask apps, it is required in the
App Template for static publishing.
"""

import app_config
import logging
import oauth
import parse_doc
import static

from copydoc import CopyDoc
from flask import Flask, make_response, render_template, jsonify
from flask_cors import CORS
from render_utils import make_context, smarty_filter, flatten_app_config
from render_utils import urlencode_filter
from werkzeug.debug import DebuggedApplication

app = Flask(__name__)
app.debug = app_config.DEBUG
CORS(app)

app.add_template_filter(smarty_filter, name='smarty')
app.add_template_filter(urlencode_filter, name='urlencode')

logging.basicConfig(format=app_config.LOG_FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(app_config.LOG_LEVEL)


@app.route('/liveblog.html', methods=['GET', 'OPTIONS'])
def _liveblog():
    """
    Liveblog only contains published posts
    """
    context = get_liveblog_context()
    return make_response(render_template('liveblog.html', **context))


@app.route('/liveblog_preview.html', methods=['GET', 'OPTIONS'])
def _preview():
    """
    Preview contains published and draft posts
    """
    context = get_liveblog_context()
    return make_response(render_template('liveblog.html', **context))


@app.route('/share.html', methods=['GET', 'OPTIONS'])
def _share():
    """
    Preview contains published and draft posts
    """
    context = get_liveblog_context()
    return make_response(render_template('share.html', **context))


@app.route('/copydoc.html', methods=['GET', 'OPTIONS'])
def _copydoc():
    """
    Example view demonstrating rendering a simple HTML page.
    """
    with open(app_config.LIVEBLOG_HTML_PATH) as f:
        html = f.read()

    doc = CopyDoc(html)
    context = {
        'doc': doc
    }

    return make_response(render_template('copydoc.html', **context))


@app.route('/child.html')
def child():
    """
    Example view demonstrating rendering a simple HTML page.
    """
    context = make_context()

    return make_response(render_template('child.html', **context))


@app.route('/')
@app.route('/index.html')
def index():
    """
    Example view demonstrating rendering a simple HTML page.
    """
    context = make_context()

    return make_response(render_template('parent.html', **context))


@app.route('/preview.html')
def preview():
    """
    Example view demonstrating rendering a simple HTML page.
    """
    context = make_context()

    return make_response(render_template('parent.html', **context))


app.register_blueprint(static.static)
app.register_blueprint(oauth.oauth)


def get_liveblog_context():
    """
    Get liveblog context
    for production we will reuse a fake g context
    in order not to perform the parsing twice
    """
    from flask import g
    context = flatten_app_config()
    parsed_liveblog_doc = getattr(g, 'parsed_liveblog', None)
    if parsed_liveblog_doc is None:
        logger.debug("did not find parsed_liveblog")
        with open(app_config.LIVEBLOG_HTML_PATH) as f:
            html = f.read()
        context.update(parse_document(html))
    else:
        logger.debug("found parsed_liveblog in g")
        context.update(parsed_liveblog_doc)
    return context


def parse_document(html):
    doc = CopyDoc(html)
    parsed_document = parse_doc.parse(doc)

    return parsed_document


# Enable Werkzeug debug pages
if app_config.DEBUG:
    wsgi_app = DebuggedApplication(app, evalex=False)
else:
    wsgi_app = app

# Catch attempts to run the app directly
if __name__ == '__main__':
    logging.error(
        'This command has been removed! Please run "fab app" instead!')
