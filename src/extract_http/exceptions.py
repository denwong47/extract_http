import www_authenticate
from requests.exceptions import Timeout, HTTPError

class ConfigIncomplete(ValueError):
    def __bool__(self):
        return False
    __nonzero__ = __bool__

class HTMLParseError(ValueError):
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