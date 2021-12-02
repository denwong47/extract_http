import warnings

import re
from concurrent.futures import ThreadPoolExecutor

from urllib.parse import urljoin
from extract_http import curl
from extract_http.bin import formatters, \
                             safe_zip

def transform_record(
    transform:dict,
    record:dict,
    url:str=None,
)->dict:

    # Allow the dict content to be a list and still apply the transformation by iteration
    def vectorise(func):
        def wrapper(*args, **kwargs):
            _source = kwargs.get("source", None)

            if (isinstance(_source, list) and not isinstance(_source, str)):
                _return = [ func(*args, **{
                        **kwargs,
                        "source":_subsource
                    } ) for _subsource in _source ]
                # with ThreadPoolExecutor() as executor:
                #     _mapper = lambda subsource: func(*args, **{
                #         **kwargs,
                #         "source":subsource
                #     } )

                #     _return = executor.map(
                #         _mapper,
                #         list(_source)
                #     )
            else:
                _return = func(*args, **kwargs)
            
            return _return

        return wrapper

    # @vectorise can't work here:
    # This is a special case where source is not the record[key] but the source str.
    # we need to look at record and figure out if any {obj} used is a list; if so, return a list capturing all of them.
    # It is assumed that if some of them are lists, they would have the same length.
    def get_source(
        source:str,
        record:dict
    ):
        # Work out if there is a list involved in the formatters
        _list_count = None
        for _formatter in formatters(source):
            if (isinstance(record.get(_formatter, None), list) and \
                not isinstance(record.get(_formatter, None), str)):
                _list_count = len(record.get(_formatter, None))
                break

        if (_list_count):
            _return = []
            
            # So we have a list to deal with.

            # First we create a generator of ( [_subrecord1_attr1, _subrecord1_attr2,... ], [_subrecord2_attr1, _subrecord2_attr2,... ], [_subrecord3_attr1, _subrecord3_attr2,... ], )
            _subrecords = safe_zip(*[record[_formatter] for _formatter in formatters(source)], repeat_last=True)
            # Using repeat_last allows anything that is not a list to be repeated.
            # This generator does not contain the formatter name itself.
            
            # So we dig into each subrecord:
            for _subrecord in _subrecords:
                # And rebuild the subrecord as a dict { attr1:_subrecord1_attr1, attr2:_subrecord1_attr2, attr3:_subrecord1_attr3,}...
                _subrecord = {
                    _key:_value \
                        for _key, _value in zip(formatters(source), _subrecord)
                }
                
                # Do the formatting
                _return.append(source.format(**_subrecord))
            
            return _return
        else:
            return source.format(**record)

    @vectorise
    def change_type(
        type:str,
        source:str,
    ):
        _type_switch = {
            "int":int,
            "str":str,
            "float":float,
            "bool":bool,
            "bytes":lambda text: text.encode("utf-8"),
        }
        try:
            _return = _type_switch.get(type, str)(source)
        except ValueError as e:
            # If failed, just return as is
            _return = source
        return _return

    # Does not need to vectorise this - ThreadPoolExecutor is embedded here
    def embed_base64(
        embed:str,
        source:str,
        url:str=None,
        params:dict=None,
    ):
        _data = []

        # Fetch URL
        if (embed == "url"):
            if (isinstance(url, str)):
                prep_url = lambda _url: urljoin(url, _url)
            else:
                prep_url = lambda _url: _url

            _urls = [ 
                prep_url(_url) for _url in ([ source, ] if isinstance(source, str) else source)
            ]
            
            with ThreadPoolExecutor() as executor:
                _data = executor.map(lambda _url:curl(_url, params, encode="base64text"), _urls)

        _data = [
            (_result if (not isinstance(_result, Exception)) else None) for _result in list(_data)
        ]

        if (isinstance(source, str)):
            if (len(_data) <= 0):
                return None
            else:
                return _data[0]
        else:
            return _data

    @vectorise
    def make_substitution(
        substitute:dict,
        source:str,
    ):
        _pattern = substitute.get("pattern", None)
        _rep = substitute.get("rep", None)

        if (None in (_pattern, _rep)):
            warnings.warn(f"Pattern '{_pattern}' or Replacement '{_rep}' not valid, skipping.")
            _return = source
        else:  
            _return = re.sub(
                _pattern,
                _rep,
                source,
            )

        return _return

    # Each _key in transform represents a new dict key
    for _key in transform:
        _source = transform[_key].get("source", None)
        _type = transform[_key].get("type", None)
        _substitute = transform[_key].get("substitute", None)
        _embed = transform[_key].get("embed", None)

        if (not(_source) and not (_key in record)):
            warnings.warn(f"Source not found for transform key {_key}, skipping.")
        else:
            if (_source is not None):
                # Create the new key if doesn't exist yet
                record[_key] = get_source(
                    source=_source,
                    record=record
                    )

            # REGEX SUBSTITUTION
            if (_substitute):
                record[_key] = make_substitution(
                    substitute=_substitute,
                    source=record[_key],
                )

            # EMBED BASE64
            if (_embed):
                record[_key] = embed_base64(
                    embed=_embed,
                    source=record[_key],
                    url=url,
                    )

            # TYPE CHANGE
            if (_type):
                record[_key] = change_type(
                    type=_type,
                    source=record[_key]
                    )
            
    return record
        