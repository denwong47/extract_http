"""
exceptions.py

All Exceptions that this module can raise.

Some Exceptions won't be raised immediately, but instead being returned, to avoid multiple layers of try-catch.
All Exceptions will bool() as False, so that the returned values can be checked for if(_return) to see if it succeeded.
"""


import www_authenticate
from requests.exceptions import Timeout, HTTPError

class ConfigIncomplete(ValueError):
    def __bool__(self):
        return False
    __nonzero__ = __bool__

class FileIOError(RuntimeError):
    def __bool__(self):
        return False
    __nonzero__ = __bool__

class HTMLParseError(ValueError):
    """
    Save the HTML if parsing resulted in error.
    Call HTMLParseError(msg, html=html) to save up the HTML.
    """

    def __init__(self, *args, html:str=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.html = html

    def __bool__(self):
        return False
    __nonzero__ = __bool__

class HTTPRequestTimedOut(Timeout):
    def __bool__(self):
        return False
    __nonzero__ = __bool__

class HTTPRequestUnknownError(RuntimeError):
    def __bool__(self):
        return False
    __nonzero__ = __bool__

class HTTPRequestError(HTTPError):
    """
    Save the error code and headers if curl resulted in an error.
    """

    def __init__(self, *args, err_code:int=None, headers:dict=None, content:str=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.err_code = err_code

        self.headers = headers
        if ("WWW-Authenticate" in self.headers):
            self.headers["WWW-Authenticate"] = www_authenticate.parse(self.headers["WWW-Authenticate"])

        self.content = content

    def __bool__(self):
        return self.err_code == 200
    __nonzero__ = __bool__