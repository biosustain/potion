from flask import _app_ctx_stack, _request_ctx_stack
from werkzeug.exceptions import NotFound
from werkzeug.urls import url_parse


def route_from(url, method=None):
    # Source: http://stackoverflow.com/questions/19129407/looking-for-inverse-of-url-for-in-flask
    appctx = _app_ctx_stack.top
    reqctx = _request_ctx_stack.top
    if appctx is None:
        raise RuntimeError('Attempted to match a URL without the '
                           'application context being pushed. This has to be '
                           'executed when application context is available.')

    if reqctx is not None:
        url_adapter = reqctx.url_adapter
    else:
        url_adapter = appctx.url_adapter
        if url_adapter is None:
            raise RuntimeError('Application was not able to create a URL '
                               'adapter for request independent URL matching. '
                               'You might be able to fix this by setting '
                               'the SERVER_NAME config variable.')
    parsed_url = url_parse(url)
    if parsed_url.netloc is not "" and parsed_url.netloc != url_adapter.server_name:
        raise NotFound()
    return url_adapter.match(parsed_url.path, method)


# --- start of Flask-RESTful code ---
# Copyright (c) 2013, Twilio, Inc.
# All rights reserved.
# This code is part of Flask-RESTful and is governed by its
# license. Please see the LICENSE file in the root of this package.
def unpack(value):
    """Return a three tuple of data, code, and headers"""
    if not isinstance(value, tuple):
        return value, 200, {}

    try:
        data, code, headers = value
        return data, code, headers
    except ValueError:
        pass

    try:
        data, code = value
        return data, code, {}
    except ValueError:
        pass

    return value, 200, {}


def get_value(key, obj, default):
    if hasattr(obj, '__getitem__'):
        try:
            return obj[key]
        except (IndexError, TypeError, KeyError):
            pass
    return getattr(obj, key, default)
# --- end of Flask-RESTful code ---


class AttributeDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
