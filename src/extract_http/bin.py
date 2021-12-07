import base64
import json
import string
import cgi, requests
from requests.exceptions import Timeout
import yaml

from extract_http.exceptions import HTTPRequestTimedOut, \
                                    HTTPRequestUnknownError, \
                                    HTTPRequestError \

# Fetch url and return in the appropriate data type
def curl(
    url:str,
    params:dict=None,
    encode:str="base64",
):
    if (not isinstance(params, dict)): params = {}

    try:
        r = requests.get(
            url,
            params=params,
        )
    except Timeout as e:
        return HTTPRequestTimedOut(str(e))
    except Exception as e: # Includes all other exceptions like requests.exceptions.ConnectionError
        return HTTPRequestUnknownError(str(e))
    
    if (r.status_code == 200):
        mime, options = cgi.parse_header(r.headers['Content-Type'])
        mimetype, mimesubtype = mime.split("/", maxsplit=1)
        
        # Return value depending on mime type.
        if (mimetype=="application"):

            # application/json
            if (mimesubtype=="json"):
                try:
                    _return = r.json() # this may fail, catch below
                except (requests.exceptions.InvalidJSONError,
                        json.decoder.JSONDecodeError) as e:
                    _return = r.text

            # application/x-yaml
            elif (mimesubtype=="x-yaml"):
                try:
                    _return = yaml.load(r.text(), Loader=yaml.CLoader)
                except yaml.YAMLError as e:
                    _return = r.text

            # application/x-httpd-php
            elif (mimesubtype in ("x-httpd-php", \
                                  "xml", \
                                 )):
                _return = r.text

            # application/*
            else:
                _return = r.content

        elif (mimetype=="image"):
            # image/*
            _return = r.content # bytes

        elif (mimetype=="text"):
            # text/*
            _return = r.text

        else:
            # bytes for everything else
            _return = r.content

        # Allow for bytes encoding.
        # Bear in mind that base64 encoded bytes are still in bytes type.
        if (isinstance(_return, bytes)):
            _bytes_switch = {
                "base64": base64.encodebytes,
                "base64text": lambda data:base64.encodebytes(data).decode("UTF-8").replace("\n",""),
                None: lambda data:data,
            }
            
            _return = _bytes_switch.get(encode, _bytes_switch[None])(_return)

        return _return
    else:
        return HTTPRequestError(f"Generic HTTP Error {r.status_code}", err_code=r.status_code, headers=r.headers, content=r.text)


# Generator yielding all formatters in a string
def formatters(format:str):
    _generator = (_formatter[1] for _formatter in string.Formatter().parse(format))
    for _yield in _generator:
        if (_yield):
            yield _yield
    
    return



class GeneratorExhausted(StopIteration):
    def __init__(self, *args, last_value):
        super().__init__(*args)
        self.last_value = last_value

    def __bool__(self):
        return False
    __nonzero__ = __bool__

    def __int__ (self):
        return None


# Safe Generator will return None indefinitely after StopIteration;
# It can also force non-iterables to yield itself once like an iterator.
def safe_generator(obj, repeat=True):
    if (hasattr(obj, "__iter__") and not isinstance(obj, str)):
        _generator = obj.__iter__
    else:
        def _generator():
            yield obj

    _last_value = None
    _generator = _generator()

    while (True):
        try:
            _last_value = next(_generator)
            yield _last_value
        except StopIteration as e:
            yield GeneratorExhausted("Generator has no more values.", last_value=_last_value)

# Safe Zip is like zip(), but it will not complain even if non-iterables are included.
# It will return None for exhausted elements.
#
# This is useful for dealing with dicts that may or may not contain NoneTypes - we are web scrapping and there are pages that we inevitably will not find the tags we want.
def safe_zip(*args, repeat_last=False):
    _generators = [safe_generator(obj) for obj in args]
    while (True):
        _return = [next(_generator) for _generator in _generators]
        if (any(_return)):
            yield tuple([ (_item if (not isinstance(_item, GeneratorExhausted)) else \
                            ( _item.last_value if repeat_last else None )) \
                 for _item in _return])
        else:
            return
