# -*- coding: utf-8 -*-


class RequestException(RuntimeError):
    """There was an exception that occurred while handling the request."""


class Timeout(RequestException):
    """The request timed out."""


class URLRequired(RequestException):
    """A valid URL is required to make a request."""


class TooManyRedirects(RequestException):
    """Too many redirection that beyond the value in default settings."""
